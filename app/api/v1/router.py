from fastapi import APIRouter

from app.api.v1.audiences import audiences_router_v1
from app.api.v1.auth import auth_router_v1
from app.api.v1.benchmark import benchmark_router_v1
from app.api.v1.journey_capture import journey_capture_router_v1
from app.api.v1.results import results_router_v1
from app.api.v1.simulations import simulations_router_v1
from app.api.v1.stimuli import stimuli_router_v1
from app.api.v1.studies import studies_router_v1
from app.api.v1.tasks import tasks_router_v1
from app.api.v1.users import users_router_v1

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router_v1)
api_router.include_router(users_router_v1)
api_router.include_router(studies_router_v1)
api_router.include_router(audiences_router_v1)
api_router.include_router(stimuli_router_v1)
api_router.include_router(tasks_router_v1)
api_router.include_router(benchmark_router_v1)
api_router.include_router(simulations_router_v1)
api_router.include_router(results_router_v1)
api_router.include_router(journey_capture_router_v1)
