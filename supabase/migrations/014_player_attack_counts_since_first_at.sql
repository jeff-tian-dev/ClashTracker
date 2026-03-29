-- Add earliest attack time in window (for "(X days of data)" on Players tab, same formula as profile).

DROP FUNCTION IF EXISTS public.player_attack_counts_since(timestamptz, text[]);

CREATE FUNCTION public.player_attack_counts_since(
    p_since timestamptz,
    p_tags text[]
)
RETURNS TABLE (player_tag text, attack_count bigint, first_attacked_at timestamptz)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    SELECT e.player_tag,
           count(*)::bigint AS attack_count,
           min(e.attacked_at) AS first_attacked_at
    FROM player_attack_events e
    WHERE e.attacked_at >= p_since
      AND e.player_tag = ANY (p_tags)
    GROUP BY e.player_tag;
$$;

COMMENT ON FUNCTION public.player_attack_counts_since(timestamptz, text[]) IS
    'Returns attack_count and earliest attacked_at per player_tag since p_since for tags in p_tags.';

GRANT EXECUTE ON FUNCTION public.player_attack_counts_since(timestamptz, text[]) TO service_role;
