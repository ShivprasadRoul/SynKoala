"""Path-string constants, one <Resource>Routes class per resource — matching
projectstruct.md's `<Feature>Routes` convention. Routers reference these instead of
inlining path strings, so the URL surface is greppable from one file. Paths are
relative to the `/api/v1` prefix added centrally in app/api/v1/router.py."""


class AuthRoutes:
    TAGS = ["auth"]
    BASE_PATH = "auth"
    FIGMA_AUTHORIZE = f"/{BASE_PATH}/figma/authorize"
    FIGMA_CALLBACK = f"/{BASE_PATH}/figma/callback"
    FIGMA_STATUS = f"/{BASE_PATH}/figma/status"


class UsersRoutes:
    TAGS = ["users"]
    BASE_PATH = "users"
    ME = f"/{BASE_PATH}/me"


class StudiesRoutes:
    TAGS = ["studies"]
    BASE_PATH = "studies"
    LIST_CREATE = f"/{BASE_PATH}"
    DETAIL = f"/{BASE_PATH}/{{study_id}}"


class AudiencesRoutes:
    TAGS = ["audience"]
    BASE_PATH = "studies/{study_id}/audience"
    LIST_CREATE = f"/{BASE_PATH}"
    GENERATE = f"/{BASE_PATH}/generate"
    PARTICIPANTS = f"/{BASE_PATH}/participants"


class StimuliRoutes:
    TAGS = ["stimulus"]
    BASE_PATH = "studies/{study_id}/stimulus"
    LIST_CREATE = f"/{BASE_PATH}"
    BULK_CREATE = f"/{BASE_PATH}/bulk"
    ANALYZE = f"/{BASE_PATH}/analyze"


class TasksRoutes:
    TAGS = ["tasks"]
    BASE_PATH = "studies/{study_id}/tasks"
    LIST_CREATE = f"/{BASE_PATH}"
    # planning/02-api.md: task update is a top-level /tasks/:taskId route, not
    # nested under study — a task's id alone is enough, ownership is still checked
    # in the use case.
    FLAT_BASE_PATH = "tasks"
    UPDATE = f"/{FLAT_BASE_PATH}/{{task_id}}"


class JourneyCaptureRoutes:
    """planning/13-journey-capture.md / LLD §18. Intended-path and human-run/session
    creation are creator-authenticated (get_current_user); observations/voice-note/
    complete are capture-token-authenticated (get_capture_token) — called by the
    mobile capture app itself, with no Supabase login."""

    TAGS = ["journey-capture"]
    TASK_BASE_PATH = "studies/{study_id}/tasks/{task_id}"
    INTENDED_PATH = f"/{TASK_BASE_PATH}/intended-path"
    HUMAN_RUNS = f"/{TASK_BASE_PATH}/human-runs"
    HUMAN_RUNS_FLAT_BASE_PATH = "human-runs"
    SESSIONS = f"/{HUMAN_RUNS_FLAT_BASE_PATH}/{{run_id}}/sessions"
    PARTICIPANT_RUNS_FLAT_BASE_PATH = "participant-runs"
    OBSERVATIONS = f"/{PARTICIPANT_RUNS_FLAT_BASE_PATH}/{{participant_run_id}}/observations"
    VOICE_NOTE = f"/{PARTICIPANT_RUNS_FLAT_BASE_PATH}/{{participant_run_id}}/voice-note"
    COMPLETE = f"/{PARTICIPANT_RUNS_FLAT_BASE_PATH}/{{participant_run_id}}/complete"


class BenchmarkRoutes:
    TAGS = ["benchmark"]
    BASE_PATH = "studies/{study_id}/benchmark"
    UPSERT_GET = f"/{BASE_PATH}"


class SimulationsRoutes:
    TAGS = ["simulations"]
    BASE_PATH = "studies/{study_id}/simulations"
    CREATE = f"/{BASE_PATH}"
    FLAT_BASE_PATH = "simulations"
    DETAIL = f"/{FLAT_BASE_PATH}/{{run_id}}"
    CANCEL = f"/{FLAT_BASE_PATH}/{{run_id}}/cancel"
    PROGRESS = f"/{FLAT_BASE_PATH}/{{run_id}}/progress"


class ResultsRoutes:
    TAGS = ["results"]
    BASE_PATH = "simulations/{run_id}"
    PARTICIPANTS = f"/{BASE_PATH}/participants"
    OBSERVATIONS = f"/{BASE_PATH}/observations"
    METRICS = f"/{BASE_PATH}/metrics"
    HEATMAP = f"/{BASE_PATH}/heatmap"
    PATHS = f"/{BASE_PATH}/paths"
    SEGMENTS = f"/{BASE_PATH}/segments"
    VALIDATION = f"/{BASE_PATH}/validation"
    INSIGHTS = f"/{BASE_PATH}/insights"
