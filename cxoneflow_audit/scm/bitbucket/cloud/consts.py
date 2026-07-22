repo_required_events = [
    "pullrequest:approved",
    "pullrequest:created",
    "pullrequest:changes_request_created",
    "pullrequest:fulfilled",
    "repo:push",
    "pullrequest:rejected",
    "pullrequest:changes_request_removed",
    "pullrequest:unapproved",
    "pullrequest:updated",
    "repo:updated",
]

ws_required_events = repo_required_events + [
    "project:updated",
    "pullrequest:push",
]
