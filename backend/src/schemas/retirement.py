from pydantic import BaseModel,Field,field_validator
class RetirementInput(BaseModel):
    field:str=Field(min_length=1,max_length=40)
    @field_validator('field')
    @classmethod
    def field_valid(cls,value):
        if not value.strip(): raise ValueError('下线字段名不能为空')
        return value
