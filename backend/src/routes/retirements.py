from fastapi import APIRouter,Depends
from src.config.database import db_session
from src.utils.security import current,writer
from src.schemas.retirement import RetirementInput
from src.services import retirements as service
router=APIRouter()
@router.get('/retirements')
def listing(db=Depends(db_session),user=Depends(current)):return service.listing(db)
@router.post('/relations/{relation_id}/retirements',status_code=201)
def create(relation_id:int,data:RetirementInput,db=Depends(db_session),user=Depends(writer)):return service.create(db,relation_id,data,user)
@router.post('/retirements/{ident}/precheck')
def precheck(ident:int,db=Depends(db_session),user=Depends(writer)):return service.precheck(db,ident,user)
@router.post('/retirements/{ident}/confirm')
def confirm(ident:int,db=Depends(db_session),user=Depends(writer)):return service.confirm(db,ident,user)
