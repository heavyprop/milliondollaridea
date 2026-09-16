WITH query_terms AS (
    SELECT value AS term
    FROM jsonb_array_elements_text($1::jsonb)
    WHERE value <> ''
),
query_labels AS (
    SELECT value ->> 'id' AS label_id
    FROM jsonb_array_elements($2::jsonb)
)
SELECT
    thread.id,
    thread.title,
    thread.description,
    COALESCE(thread.topic_labels, '[]'::jsonb) AS topic_labels,
    thread.created_at,
    thread.likes,
    (
        SELECT COUNT(*)
        FROM home_comment AS comment
        WHERE comment.thread_id = thread.id
    ) AS comment_count,
    (
        SELECT COUNT(*)
        FROM home_threadview AS thread_view
        WHERE thread_view.thread_id = thread.id
    ) AS view_count
FROM home_thread AS thread
WHERE
    EXISTS (
        SELECT 1
        FROM query_terms
        WHERE
            STRPOS(LOWER(thread.title), LOWER(term)) > 0
            OR STRPOS(LOWER(thread.description), LOWER(term)) > 0
    )
    OR EXISTS (
        SELECT 1
        FROM query_labels
        WHERE thread.topic_labels @> jsonb_build_array(
            jsonb_build_object('id', label_id)
        )
    )
ORDER BY thread.id;
