-- Bind attack/defense window limit via scalar subqueries so p_max_attacks is never
-- ambiguous inside RETURNS TABLE bodies (fixes window having no effect for some callers).

CREATE OR REPLACE FUNCTION public.war_player_leaderboard_stats(
    p_clan_tag text,
    p_max_attacks integer DEFAULT NULL
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
    WITH scoped_wars AS (
        SELECT
            w.id,
            COALESCE(w.attacks_per_member, 0)::bigint AS apm,
            w.start_time
        FROM wars w
        WHERE w.clan_tag = p_clan_tag
          AND w.state = 'warEnded'
    ),
    raw_wa AS (
        SELECT
            wa.war_id,
            wa.attacker_tag,
            wa.defender_tag,
            wa.stars,
            wa.destruction_percentage,
            wa.is_home_attacker,
            wa.attack_order,
            sw.start_time,
            sw.apm
        FROM war_attacks wa
        INNER JOIN scoped_wars sw ON sw.id = wa.war_id
        WHERE wa.is_home_attacker IS NOT NULL
    ),
    off_ranked AS (
        SELECT
            rw.attacker_tag AS tag,
            rw.war_id,
            rw.stars,
            rw.destruction_percentage,
            row_number() OVER (
                PARTITION BY rw.attacker_tag
                ORDER BY rw.start_time DESC NULLS LAST, rw.war_id DESC, rw.attack_order DESC NULLS LAST
            ) AS rn_off
        FROM raw_wa rw
        WHERE rw.is_home_attacker = true
    ),
    off_window AS (
        SELECT o.tag, o.war_id, o.stars, o.destruction_percentage
        FROM off_ranked o
        WHERE (SELECT p_max_attacks) IS NULL OR o.rn_off <= (SELECT p_max_attacks)
    ),
    def_ranked AS (
        SELECT
            rw.defender_tag AS tag,
            rw.war_id,
            rw.stars,
            rw.destruction_percentage,
            row_number() OVER (
                PARTITION BY rw.defender_tag
                ORDER BY rw.start_time DESC NULLS LAST, rw.war_id DESC, rw.attack_order DESC NULLS LAST
            ) AS rn_def
        FROM raw_wa rw
        WHERE rw.is_home_attacker = false
    ),
    def_window AS (
        SELECT d.tag, d.war_id, d.stars, d.destruction_percentage
        FROM def_ranked d
        WHERE (SELECT p_max_attacks) IS NULL OR d.rn_def <= (SELECT p_max_attacks)
    ),
    offense_agg AS (
        SELECT
            ow.tag,
            count(*)::bigint AS offense_count,
            avg(ow.stars)::numeric AS avg_offense_stars,
            avg(ow.destruction_percentage)::numeric AS avg_offense_destruction
        FROM off_window ow
        WHERE NOT (ow.stars = 1 AND ow.destruction_percentage < 40::numeric)
        GROUP BY ow.tag
    ),
    defense_agg AS (
        SELECT
            dw.tag,
            count(*)::bigint AS defense_count,
            avg(dw.stars)::numeric AS avg_defense_stars,
            avg(dw.destruction_percentage)::numeric AS avg_defense_destruction
        FROM def_window dw
        WHERE NOT (dw.stars = 1 AND dw.destruction_percentage < 40::numeric)
        GROUP BY dw.tag
    ),
    participation_pairs AS (
        SELECT DISTINCT u.tag, u.war_id
        FROM (
            SELECT ow.tag, ow.war_id FROM off_window ow
            UNION
            SELECT dw.tag, dw.war_id FROM def_window dw
        ) u
    ),
    participation_stats AS (
        SELECT
            pp.tag,
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
    'Per-player war stats for one clan (ended wars). p_max_attacks NULL = all attacks; else last N offensive swings and last N defensive rows (by recency). Omits farming from aggregates (1 star, dest < 40%). Missed = expected slots in scoped wars minus non-farming home attacks.';

CREATE OR REPLACE FUNCTION public.war_player_attack_history(
    p_clan_tag text,
    p_player_tag text,
    p_max_attacks integer DEFAULT NULL
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
    WITH scoped_wars AS (
        SELECT
            w.id,
            COALESCE(w.attacks_per_member, 0)::bigint AS apm,
            w.start_time,
            w.opponent_name
        FROM wars w
        WHERE w.clan_tag = p_clan_tag
          AND w.state = 'warEnded'
    ),
    off_src AS (
        SELECT
            wa.war_id,
            wa.stars,
            wa.destruction_percentage,
            wa.attack_order,
            wa.duration,
            wa.attacker_tag,
            wa.defender_tag,
            wa.is_home_attacker,
            sw.start_time,
            sw.opponent_name,
            row_number() OVER (
                ORDER BY sw.start_time DESC NULLS LAST, wa.war_id DESC, wa.attack_order DESC NULLS LAST
            ) AS rn_off
        FROM war_attacks wa
        INNER JOIN scoped_wars sw ON sw.id = wa.war_id
        WHERE wa.is_home_attacker IS NOT NULL
          AND wa.is_home_attacker = true
          AND wa.attacker_tag = p_player_tag
    ),
    off_scoped AS (
        SELECT *
        FROM off_src
        WHERE (SELECT p_max_attacks) IS NULL OR rn_off <= (SELECT p_max_attacks)
    ),
    def_src AS (
        SELECT
            wa.war_id,
            wa.stars,
            wa.destruction_percentage,
            wa.attack_order,
            wa.duration,
            wa.attacker_tag,
            wa.defender_tag,
            wa.is_home_attacker,
            sw.start_time,
            sw.opponent_name,
            row_number() OVER (
                ORDER BY sw.start_time DESC NULLS LAST, wa.war_id DESC, wa.attack_order DESC NULLS LAST
            ) AS rn_def
        FROM war_attacks wa
        INNER JOIN scoped_wars sw ON sw.id = wa.war_id
        WHERE wa.is_home_attacker IS NOT NULL
          AND wa.is_home_attacker = false
          AND wa.defender_tag = p_player_tag
    ),
    def_scoped AS (
        SELECT *
        FROM def_src
        WHERE (SELECT p_max_attacks) IS NULL OR rn_def <= (SELECT p_max_attacks)
    ),
    player_scoped_war_ids AS (
        SELECT DISTINCT war_id FROM off_scoped
        UNION
        SELECT DISTINCT war_id FROM def_scoped
    ),
    used_non_farming AS (
        SELECT
            wa.war_id,
            count(*)::bigint AS used_n
        FROM war_attacks wa
        INNER JOIN player_scoped_war_ids psw ON psw.war_id = wa.war_id
        WHERE wa.is_home_attacker = true
          AND wa.attacker_tag = p_player_tag
          AND wa.is_home_attacker IS NOT NULL
          AND NOT (wa.stars = 1 AND wa.destruction_percentage < 40::numeric)
        GROUP BY wa.war_id
    ),
    war_miss AS (
        SELECT
            sw.id AS war_id,
            greatest(0, sw.apm - COALESCE(unf.used_n, 0))::integer AS missed_n
        FROM scoped_wars sw
        INNER JOIN player_scoped_war_ids psw ON psw.war_id = sw.id
        LEFT JOIN used_non_farming unf ON unf.war_id = sw.id
    ),
    missed_expanded AS (
        SELECT
            'missed'::text AS kind,
            sw.id AS war_id,
            sw.start_time,
            sw.opponent_name,
            NULL::int AS stars,
            NULL::numeric AS destruction_percentage,
            (2000000 + gs.i)::int AS attack_order,
            NULL::int AS duration,
            p_player_tag AS attacker_tag,
            ''::text AS defender_tag,
            true AS is_home_attacker
        FROM war_miss wm
        INNER JOIN scoped_wars sw ON sw.id = wm.war_id
        CROSS JOIN LATERAL generate_series(1, wm.missed_n) AS gs(i)
    ),
    offense_rows AS (
        SELECT
            'offense'::text AS kind,
            o.war_id,
            o.start_time,
            o.opponent_name,
            o.stars::int,
            o.destruction_percentage,
            o.attack_order,
            o.duration,
            o.attacker_tag,
            o.defender_tag,
            o.is_home_attacker
        FROM off_scoped o
    ),
    defense_rows AS (
        SELECT
            'defense'::text AS kind,
            d.war_id,
            d.start_time,
            d.opponent_name,
            d.stars::int,
            d.destruction_percentage,
            d.attack_order,
            d.duration,
            d.attacker_tag,
            d.defender_tag,
            d.is_home_attacker
        FROM def_scoped d
    )
    SELECT * FROM (
        SELECT * FROM offense_rows
        UNION ALL
        SELECT * FROM missed_expanded
        UNION ALL
        SELECT * FROM defense_rows
    ) u
    ORDER BY u.start_time DESC NULLS LAST, u.war_id DESC, u.attack_order ASC NULLS LAST;
$$;

COMMENT ON FUNCTION public.war_player_attack_history(text, text, integer) IS
    'War rows for one player: offense (incl. farming), synthetic missed slots, defense. p_max_attacks limits last N offense rows and last N defense rows; missed rows only for wars in that scope.';

GRANT EXECUTE ON FUNCTION public.war_player_leaderboard_stats(text, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.war_player_attack_history(text, text, integer) TO service_role;
