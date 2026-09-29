-- Supabase SQL Schema for Do&Go List Maker

-- 1. Profiles Table (Auth.users ile senkronize profil bilgileri)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Case-insensitive (büyük/küçük harf duyarsız) benzersiz indeksler
CREATE UNIQUE INDEX IF NOT EXISTS profiles_username_lower_idx ON public.profiles (LOWER(username));
CREATE UNIQUE INDEX IF NOT EXISTS profiles_email_lower_idx ON public.profiles (LOWER(email));

-- Profiles tablosunu yeni kullanıcı kaydolduğunda otomatik tetikleyen fonksiyon
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, username, email)
    VALUES (
        NEW.id,
        LOWER(COALESCE(NEW.raw_user_meta_data->>'username', split_part(NEW.email, '@', 1))),
        LOWER(NEW.email)
    )
    ON CONFLICT (id) DO UPDATE
    SET username = EXCLUDED.username,
        email = EXCLUDED.email;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger tanımı
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 2. Lists Table
CREATE TABLE IF NOT EXISTS public.lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    is_shared BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. ListItems Table
CREATE TABLE IF NOT EXISTS public.list_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id UUID NOT NULL REFERENCES public.lists(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    location_url TEXT,
    is_completed BOOLEAN DEFAULT false NOT NULL,
    created_by UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 4. ListPermissions Table (İleriki fazlar için hazır altyapı)
CREATE TABLE IF NOT EXISTS public.list_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id UUID NOT NULL REFERENCES public.lists(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    can_edit BOOLEAN DEFAULT true NOT NULL,
    can_delete BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (list_id, user_id)
);

-- 5. Feedbacks Table (İleriki fazlar için hazır altyapı)
CREATE TABLE IF NOT EXISTS public.feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES public.list_items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    rating SMALLINT CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (item_id, user_id)
);

-- RLS (Row Level Security) Etkinleştirme
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.list_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.list_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedbacks ENABLE ROW LEVEL SECURITY;

-- Temel RLS Politikaları
-- Profiles
DROP POLICY IF EXISTS "Public profiles are viewable by everyone" ON public.profiles;
CREATE POLICY "Public profiles are viewable by everyone" ON public.profiles FOR SELECT USING (true);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile" ON public.profiles FOR UPDATE USING (auth.uid() = id);

-- Lists
DROP POLICY IF EXISTS "Users can view own lists or shared lists" ON public.lists;
CREATE POLICY "Users can view own lists or shared lists" ON public.lists FOR SELECT USING (
    auth.uid() = owner_id OR is_shared = true OR EXISTS (
        SELECT 1 FROM public.list_permissions WHERE list_id = public.lists.id AND user_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Users can insert own lists" ON public.lists;
CREATE POLICY "Users can insert own lists" ON public.lists FOR INSERT WITH CHECK (auth.uid() = owner_id);

DROP POLICY IF EXISTS "Users can update own lists" ON public.lists;
CREATE POLICY "Users can update own lists" ON public.lists FOR UPDATE USING (auth.uid() = owner_id);

DROP POLICY IF EXISTS "Users can delete own lists" ON public.lists;
CREATE POLICY "Users can delete own lists" ON public.lists FOR DELETE USING (auth.uid() = owner_id);

-- List Items
DROP POLICY IF EXISTS "Users can view items of accessible lists" ON public.list_items;
CREATE POLICY "Users can view items of accessible lists" ON public.list_items FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM public.lists WHERE id = public.list_items.list_id AND (
            owner_id = auth.uid() OR is_shared = true OR EXISTS (
                SELECT 1 FROM public.list_permissions WHERE list_id = public.lists.id AND user_id = auth.uid()
            )
        )
    )
);

DROP POLICY IF EXISTS "Users can insert items to accessible lists" ON public.list_items;
CREATE POLICY "Users can insert items to accessible lists" ON public.list_items FOR INSERT WITH CHECK (
    EXISTS (
        SELECT 1 FROM public.lists WHERE id = public.list_items.list_id AND (
            owner_id = auth.uid() OR EXISTS (
                SELECT 1 FROM public.list_permissions WHERE list_id = public.lists.id AND user_id = auth.uid() AND can_edit = true
            )
        )
    )
);

DROP POLICY IF EXISTS "Users can update items in accessible lists" ON public.list_items;
CREATE POLICY "Users can update items in accessible lists" ON public.list_items FOR UPDATE USING (
    EXISTS (
        SELECT 1 FROM public.lists WHERE id = public.list_items.list_id AND (
            owner_id = auth.uid() OR EXISTS (
                SELECT 1 FROM public.list_permissions WHERE list_id = public.lists.id AND user_id = auth.uid() AND can_edit = true
            )
        )
    )
);

DROP POLICY IF EXISTS "Users can delete items in accessible lists" ON public.list_items;
CREATE POLICY "Users can delete items in accessible lists" ON public.list_items FOR DELETE USING (
    EXISTS (
        SELECT 1 FROM public.lists WHERE id = public.list_items.list_id AND (
            owner_id = auth.uid() OR EXISTS (
                SELECT 1 FROM public.list_permissions WHERE list_id = public.lists.id AND user_id = auth.uid() AND can_delete = true
            )
        )
    )
);
