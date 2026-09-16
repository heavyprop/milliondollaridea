def build_comment_tree(comments):
    comments_by_parent = {}

    for comment in comments:
        comment.children = []
        comments_by_parent.setdefault(comment.parent_id, []).append(comment)

    for comment in comments:
        comment.children = comments_by_parent.get(comment.id, [])

    return comments_by_parent.get(None, [])
