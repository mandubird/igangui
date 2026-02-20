-- 제작자 공식 답변 기능 — Supabase 설치 스크립트
-- Supabase 대시보드 → SQL Editor에서 순서대로 실행하세요.

-- 2-1. creator_responses
CREATE TABLE creator_responses (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id     UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  creator_id    UUID NOT NULL,
  content       TEXT NOT NULL CHECK (char_length(content) BETWEEN 10 AND 1000),
  is_visible    BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_response_per_course ON creator_responses (course_id, creator_id);
CREATE INDEX idx_creator_responses_course ON creator_responses (course_id);

-- 2-2. creator_tokens
CREATE TABLE creator_tokens (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token        TEXT NOT NULL UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
  creator_id   UUID NOT NULL,
  course_id    UUID NOT NULL,
  used         BOOLEAN NOT NULL DEFAULT false,
  expires_at   TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '72 hours'),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- (WHERE에 now() 사용 불가 → 미사용 토큰만 인덱스)
CREATE INDEX idx_creator_tokens_token ON creator_tokens (token) WHERE used = false;

-- 2-3. creator_applications
CREATE TABLE creator_applications (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id    UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  email        TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_creator_applications_status ON creator_applications (status, created_at DESC);

-- 2-4. RLS
ALTER TABLE creator_responses ENABLE ROW LEVEL SECURITY;
CREATE POLICY "공개 답변 읽기" ON creator_responses FOR SELECT USING (is_visible = true);

ALTER TABLE creator_tokens ENABLE ROW LEVEL SECURITY;

ALTER TABLE creator_applications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "신청서 제출" ON creator_applications FOR INSERT WITH CHECK (true);

-- 2-5. RPC 함수 3개
CREATE OR REPLACE FUNCTION get_creator_response(target_course_id UUID)
RETURNS TABLE (content TEXT, created_at TIMESTAMPTZ)
LANGUAGE sql STABLE AS $$
  SELECT content, created_at FROM creator_responses
  WHERE course_id = target_course_id AND is_visible = true LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION verify_creator_token(input_token TEXT)
RETURNS JSON LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE rec creator_tokens%ROWTYPE;
BEGIN
  SELECT * INTO rec FROM creator_tokens
  WHERE token = input_token AND used = false AND expires_at > now() LIMIT 1;
  IF NOT FOUND THEN
    RETURN json_build_object('error', true, 'message', '유효하지 않은 링크입니다');
  END IF;
  RETURN json_build_object('creator_id', rec.creator_id, 'course_id', rec.course_id);
END;
$$;

CREATE OR REPLACE FUNCTION submit_creator_response(input_token TEXT, input_content TEXT)
RETURNS JSON LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE rec creator_tokens%ROWTYPE;
BEGIN
  SELECT * INTO rec FROM creator_tokens
  WHERE token = input_token AND used = false AND expires_at > now() LIMIT 1;
  IF NOT FOUND THEN
    RETURN json_build_object('success', false, 'message', '링크가 만료되었거나 이미 사용되었습니다');
  END IF;
  INSERT INTO creator_responses (course_id, creator_id, content)
  VALUES (rec.course_id, rec.creator_id, input_content)
  ON CONFLICT (course_id, creator_id) DO UPDATE SET content = EXCLUDED.content, updated_at = now();
  UPDATE creator_tokens SET used = true WHERE token = input_token;
  RETURN json_build_object('success', true);
END;
$$;
