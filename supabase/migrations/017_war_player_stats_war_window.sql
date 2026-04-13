-- Optional last-N wars window for leaderboard + player history (by start_time DESC).

DROP FUNCTION IF EXISTS public.war_player_leaderboard_stats(text);
DROP FUNCTION IF EXISTS public.war_player_attack_history(text, text);

CREATE OR REPLACE FUNCTION public.war_player_leaderboard_stats(
    p_clan_tag text,
    p_max_wars integer DEFAULT NULL
)
RETURNS TABLE (
    player_tag text,
    player_name text,
    offense_count bigint,
    avg_offense_stars numeric,
    avg_offense_destruction numeric,
    defense_count bigint,
    avg_defense_stars numeric,
    avg_defense_destruction numeric,
    wars_participated bigint,
    attacks_missed bigint
)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    WITH ranked_wars AS (
        SELECT
            w.id,
            COALESCE(w.attacks_per_member, 0)::bigint AS apm,
            row_number() OVER (
                ORDER BY w.start_time DESC NULLS LAST, w.id DESC
            ) AS rn
        FROM wars w
        WHERE w.clan_tag = p_clan_tag
          AND w.state = 'warEnded'
    ),
    scoped_wars AS (
        SELECT rw.id, rw.apm
        FROM ranked_wars rw
        WHERE p_max_wars IS NULL OR rw.rn <= p_max_wars
    ),
    filtered_attacks AS (
        SELECT wa.war_id, wa.attacker_tag, wa.defender_tag, wa.stars,
               wa.destruction_percentage, wa.is_home_attacker
        FROM war_attacks wa
        INNER JOIN scoped_wars sw ON sw.id = wa.war_id
        WHERE wa.is_home_attacker IS NOT NULL
          AND NOT (wa.stars = 1 AND wa.destruction_percentage < 40::numeric)
    ),
    offense_agg AS (
        SELECT fa.attacker_tag AS tag,
               count(*)::bigint AS offense_count,
               avg(fa.stars)::numeric AS avg_offense_stars,
               avg(fa.destruction_percentage)::numeric AS avg_offense_destruction
        FROM filtered_attacks fa
        WHERE fa.is_home_attacker = true
        GROUP BY fa.attacker_tag
    ),
    defense_agg AS (
        SELECT fa.defender_tag AS tag,
               count(*)::bigint AS defense_count,
               avg(fa.stars)::numeric AS avg_defense_stars,
               avg(fa.destruction_percentage)::numeric AS avg_defense_destruction
        FROM filtered_attacks fa
        WHERE fa.is_home_attacker = false
        GROUP BY fa.defender_tag
    ),
    participation_pairs AS (
        SELECT DISTINCT fa.attacker_tag AS tag, fa.war_id
        FROM filtered_attacks fa
        WHERE fa.is_home_attacker = true
        UNION
        SELECT DISTINCT fa.defender_tag AS tag, fa.war_id
        FROM filtered_attacks fa
        WHERE fa.is_home_attacker = false
    ),
    participation_stats AS (
        SELECT pp.tag,
               count(DISTINCT pp.war_id)::bigint AS wars_participated,
               COALESCE(sum(sw.apm), 0)::bigint AS expected_attacks
        FROM participation_pairs pp
        INNER JOIN scoped_wars sw ON sw.id = pp.war_id
        GROUP BY pp.tag
    ),
    all_tags AS (
        SELECT o.tag FROM offense_agg o
        UNION
        SELECT d.tag FROM defense_agg d
        UNION
        SELECT p.tag FROM participation_stats p
    )
    SELECT
        t.tag AS player_tag,
        COALESCE(pl.name, t.tag) AS player_name,
        COALESCE(o.offense_count, 0)::bigint,
        o.avg_offense_stars,
        o.avg_offense_destruction,
        COALESCE(d.defense_count, 0)::bigint,
        d.avg_defense_stars,
        d.avg_defense_destruction,
        COALESCE(ps.wars_participated, 0)::bigint,
        greatest(
            0,
            COALESCE(ps.expected_attacks, 0) - COALESCE(o.offense_count, 0)
        )::bigint AS attacks_missed
    FROM all_tags t
    LEFT JOIN offense_agg o ON o.tag = t.tag
    LEFT JOIN defense_agg d ON d.tag = t.tag
    LEFT JOIN participation_stats ps ON ps.tag = t.tag
    LEFT JOIN players pl ON pl.tag = t.tag;
$$;

COMMENT ON FUNCTION public.war_player_leaderboard_stats(text, integer) IS
    'Per-player war stats for one clan (ended wars). p_max_wars NULL = all wars; else last N by start_time. Omits farming hits (1★, dest < 40%).';

CREATE OR REPLACE FUNCTION public.war_player_attack_history(
    p_clan_tag text,
    p_player_tag text,
    p_max_wars integer DEFAULT NULL
)
RETURNS TABLE (
    kind text,
    war_id bigint,
    start_time timestamptz,
    opponent_name text,
    stars int,
    destruction_percentage numeric,
    attack_order int,
    duration int,
    attacker_tag text,
    defender_tag text,
    is_home_attacker boolean
)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    WITH ranked_wars AS (
        SELECT
            w.id,
            row_number() OVER (
                ORDER BY w.start_time DESC NULLS LAST, w.id DESC
            ) AS rn
        FROM wars w
        WHERE w.clan_tag = p_clan_tag
          AND w.state = 'warEnded'
    ),
    scoped_wars AS (
        SELECT rw.id FROM ranked_wars rw
        WHERE p_max_wars IS NULL OR rw.rn <= p_max_wars
    )
    SELECT
        CASE
            WHEN wa.is_home_attacker AND wa.attacker_tag = p_player_tag THEN 'offense'
            ELSE 'defense'
        END AS kind,
        w.id,
        w.start_time,
        w.opponent_name,
        wa.stars::int,
        wa.destruction_percentage,
        wa.attack_order,
        wa.duration,
        wa.attacker_tag,
        wa.defender_tag,
        wa.is_home_attacker
    FROM war_attacks wa
    INNER JOIN wars w ON w.id = wa.war_id
    INNER JOIN scoped_wars sw ON sw.id = w.id
    WHERE wa.is_home_attacker IS NOT NULL
      AND (
          (wa.is_home_attacker = true AND wa.attacker_tag = p_player_tag)
          OR (wa.is_home_attacker = false AND wa.defender_tag = p_player_tag)
      )
    ORDER BY w.start_time DESC NULLS LAST, wa.attack_order;
$$;

COMMENT ON FUNCTION public.war_player_attack_history(text, text, integer) IS
    'War attack rows for one player; p_max_wars NULL = all ended wars for clan, else last N by start_time.';

GRANT EXECUTE ON FUNCTION public.war_player_leaderboard_stats(text, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.war_player_attack_history(text, text, integer) TO service_role;
