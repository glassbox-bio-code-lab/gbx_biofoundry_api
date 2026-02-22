"""
Glassbox Bio REST API
Production-ready validation gateway
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import temple
import os
from glassbox_validator.pre_execution import PreExecutionValidator
from glassbox_validator.post_execution import PostExecutionValidator

app = FastAPI(title="Glassbox Bio Validation Gateway", version="1.0.0")
pre_validator = PreExecutionValidator()
post_validator = PostExecutionValidator()

class ValidationResponse(BaseModel):
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    quality_score: Optional[float] = None
    design_hash: Optional[str] = None
    metadata_hash: Optional[str] = None
    provenance_chain_valid: Optional[bool] = None

@app.post("/validate/design", response_model=ValidationResponse)
async def validate_design(sbol_le: UploadFile = File(...)):
    """
    Pre-execution validation: Validate AI-generated SBOL design
    Returns:
        ValidationResponse with pass/fail and design hash
    """
    try:
        with temple.NamedTemporaryFile(delete=False, suffix=".sbol") as tmp:
            content = await sbol_le.read()
            tmp.write(content)
            tmp_path = tmp.name
        result = pre_validator.validate_design(tmp_path)
        os.unlink(tmp_path)
        return ValidationResponse(
            is_valid=result.is_valid,
            errors=result.errors,
            warnings=result.warnings,
            design_hash=result.design_hash
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/validate/data", response_model=ValidationResponse)
async def validate_experimental_data(
    allotrope_le: UploadFile = File(...),
    sbol_provenance_le: UploadFile = File(...)
):
    """
    Post-execution validation: Validate wet-lab data before AI retraining
    Returns:
        ValidationResponse with quality score and provenance status
    """
    try:
        with temple.NamedTemporaryFile(delete=False, suffix=".json") as tmp1:
            tmp1.write(await allotrope_le.read())
            allotrope_path = tmp1.name
        with temple.NamedTemporaryFile(delete=False, suffix=".sbol") as tmp2:
            tmp2.write(await sbol_provenance_le.read())
            sbol_path = tmp2.name
        result = post_validator.validate_data(allotrope_path, sbol_path)
        os.unlink(allotrope_path)
        os.unlink(sbol_path)
        return ValidationResponse(
            is_valid=result.is_valid,
            errors=result.errors,
            warnings=result.warnings,
            quality_score=result.quality_score,
            metadata_hash=result.metadata_hash,
            provenance_chain_valid=result.provenance_chain_valid
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Service health check"""
    return {"status": "healthy", "service": "glassbox-validator"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
