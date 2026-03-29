-- Accurate per-player attack counts for a time window (used by GET /api/players attacks_7d).
-- Batched SELECT of raw rows hit PostgREST default max-rows (~1000), undercounting or zeroing players.

CREATE OR REPLACE FUNCTION public.player_attack_counts_since(
    p_since timestamptz,
    p_tags text[]
)
RETURNS TABLE (player_tag text, attack_count bigint)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    SELECT e.player_tag, count(*)::bigint AS attack_count
    FROM player_attack_events e
    WHERE e.attacked_at >= p_since
      AND e.player_tag = ANY (p_tags)
    GROUP BY e.player_tag;
$$;

COMMENT ON FUNCTION public.player_attack_counts_since(timestamptz, text[]) IS
    'Returns attack event counts per player_tag since p_since for tags in p_tags; avoids row-limit client counts.';

GRANT EXECUTE ON FUNCTION public.player_attack_counts_since(timestamptz, text[]) TO service_role;
