from fastapi import APIRouter, Request
from app.services.csv_service import CSVService
from app.models.schemas import ZHVIResponse
from fastapi.responses import JSONResponse
from app.core.security import auth_middleware

router = APIRouter()
csv_service = CSVService("./data/City_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")

@router.get("/zhvi/{region_name}/{state_name}", response_model=ZHVIResponse)
@auth_middleware.requires_auth
async def get_zhvi_data(request: Request, region_name: str, state_name: str):
    dates, region_data = csv_service.get_zhvi_data(region_name, state_name)
    return JSONResponse({
        "dates": dates,
        "regionData": [region_data]
    })



# from fastapi import APIRouter
# from app.services.csv_service import CSVService
# from app.models.schemas import ZHVIResponse
# from fastapi.responses import JSONResponse

# router = APIRouter()
# csv_service = CSVService("./data/City_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")

# @router.get("/zhvi/{region_name}/{state_name}", response_model=ZHVIResponse)
# async def get_zhvi_data(region_name: str, state_name: str):
#     dates, region_data = csv_service.get_zhvi_data(region_name, state_name)
#     return JSONResponse({
#         "dates": dates,
#         "regionData": [region_data]
#     })