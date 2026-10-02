-- ==============================================================================
-- DO&GO LIST MAKER - TAM VE GÜVENLİ VERİTABANI ŞEMASI (SUPABASE SQL)
-- ==============================================================================

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
    is_public BOOLEAN DEFAULT false NOT NULL,
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
    list_type TEXT DEFAULT 'GO' NOT NULL,      -- 'GO' veya 'DO'
    tag TEXT DEFAULT 'cafe',                   -- 'cafe', 'restaurant', 'museum', 'travel', 'movie', 'series', 'book', 'shopping', 'other'
    media_platform TEXT,                       -- 'Netflix', 'Disney+', 'Prime', 'HBO', 'AppleTV', 'YouTube', 'Cinema', 'Other'
    market_name TEXT,                          -- 'Migros', 'Trendyol', 'Ikea' vb.
    created_by UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Kolonların mevcut tabloda da var olmasını garanti altına alan geçiş komutları:
ALTER TABLE public.list_items ADD COLUMN IF NOT EXISTS list_type TEXT DEFAULT 'GO';
ALTER TABLE public.list_items ADD COLUMN IF NOT EXISTS tag TEXT DEFAULT 'cafe';
ALTER TABLE public.list_items ADD COLUMN IF NOT EXISTS media_platform TEXT;
ALTER TABLE public.list_items ADD COLUMN IF NOT EXISTS market_name TEXT;

-- 4. ListPermissions Table
CREATE TABLE IF NOT EXISTS public.list_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id UUID NOT NULL REFERENCES public.lists(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    can_delete BOOLEAN DEFAULT false NOT NULL,
    permission_level TEXT DEFAULT 'edit' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (list_id, user_id)
);

-- 5. Feedbacks Table
CREATE TABLE IF NOT EXISTS public.feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES public.list_items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    rating NUMERIC(2, 1) CHECK (rating >= 0.5 AND rating <= 5.0),
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

-- ------------------------------------------------------------------------------
-- DÖNGÜSÜZ & GÜVENLİ RLS POLİTİKALARI
-- ------------------------------------------------------------------------------

-- Profiles
DROP POLICY IF EXISTS "Public profiles are viewable by everyone" ON public.profiles;
CREATE POLICY "Public profiles are viewable by everyone" ON public.profiles FOR SELECT USING (true);

DROP POLICY IF EXISTS "Users can insert own profile" ON public.profiles;
CREATE POLICY "Users can insert own profile" ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile" ON public.profiles FOR UPDATE USING (auth.uid() = id);

-- Lists
DROP POLICY IF EXISTS "Lists select policy" ON public.lists;
CREATE POLICY "Lists select policy" ON public.lists FOR SELECT USING (
    auth.uid() = owner_id 
    OR is_shared = true 
    OR is_public = true
);

DROP POLICY IF EXISTS "Lists insert policy" ON public.lists;
CREATE POLICY "Lists insert policy" ON public.lists FOR INSERT TO authenticated WITH CHECK (auth.uid() = owner_id);

DROP POLICY IF EXISTS "Lists update policy" ON public.lists;
CREATE POLICY "Lists update policy" ON public.lists FOR UPDATE TO authenticated USING (auth.uid() = owner_id);

DROP POLICY IF EXISTS "Lists delete policy" ON public.lists;
CREATE POLICY "Lists delete policy" ON public.lists FOR DELETE TO authenticated USING (auth.uid() = owner_id);

-- List Permissions
DROP POLICY IF EXISTS "Permissions select policy" ON public.list_permissions;
CREATE POLICY "Permissions select policy" ON public.list_permissions FOR SELECT TO authenticated USING (
    user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM public.lists WHERE lists.id = list_permissions.list_id AND lists.owner_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Permissions insert policy" ON public.list_permissions;
CREATE POLICY "Permissions insert policy" ON public.list_permissions FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "Permissions delete policy" ON public.list_permissions;
CREATE POLICY "Permissions delete policy" ON public.list_permissions FOR DELETE TO authenticated USING (
    user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM public.lists WHERE lists.id = list_permissions.list_id AND lists.owner_id = auth.uid()
    )
);

-- List Items
DROP POLICY IF EXISTS "List items select policy" ON public.list_items;
CREATE POLICY "List items select policy" ON public.list_items FOR SELECT USING (true);

DROP POLICY IF EXISTS "List items insert policy" ON public.list_items;
CREATE POLICY "List items insert policy" ON public.list_items FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "List items update policy" ON public.list_items;
CREATE POLICY "List items update policy" ON public.list_items FOR UPDATE TO authenticated USING (true);

DROP POLICY IF EXISTS "List items delete policy" ON public.list_items;
CREATE POLICY "List items delete policy" ON public.list_items FOR DELETE TO authenticated USING (true);

-- Feedbacks
DROP POLICY IF EXISTS "Feedbacks select policy" ON public.feedbacks;
CREATE POLICY "Feedbacks select policy" ON public.feedbacks FOR SELECT USING (true);

DROP POLICY IF EXISTS "Feedbacks insert policy" ON public.feedbacks;
CREATE POLICY "Feedbacks insert policy" ON public.feedbacks FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Feedbacks update policy" ON public.feedbacks;
CREATE POLICY "Feedbacks update policy" ON public.feedbacks FOR UPDATE TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Feedbacks delete policy" ON public.feedbacks;
CREATE POLICY "Feedbacks delete policy" ON public.feedbacks FOR DELETE TO authenticated USING (auth.uid() = user_id);
