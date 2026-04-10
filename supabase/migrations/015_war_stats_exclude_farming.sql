-- Exclude "farming" hits (1 star and <40% destruction) from war player leaderboard aggregates.

CREATE OR REPLACE FUNCTION public.war_player_leaderboard_stats(p_clan_tag text)
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
    WITH scoped_wars AS (
        SELECT w.id, COALESCE(w.attacks_per_member, 0)::bigint AS apm
        FROM wars w
        WHERE w.clan_tag = p_clan_tag
          AND w.state = 'warEnded'
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

COMMENT ON FUNCTION public.war_player_leaderboard_stats(text) IS
    'Per-player war stats for ended wars of one clan; requires is_home_attacker. Omits farming hits (1 star and destruction < 40%).';
