from pathlib import Path
import logging











from fastapi import FastAPI, File, Form, HTTPException, UploadFile





from pydantic import BaseModel, ConfigDict, Field, model_validator











from app.services.document_chunker import chunk_processed_document





from app.services.document_processor import process_pdf_document





from app.services.document_service import save_uploaded_document
from app.services.registry_backend import (
    analyze_enterprise_document_relationship,
    register_enterprise_document,
)





from app.services.abb_retrieval_service import (





    retrieve_abb_records,





    retrieve_confirmed_abb_symptom,





)





from app.services.retrieval_service import (
    retrieve_enterprise_sections_configured,
    retrieve_sections,
)

















logger = logging.getLogger(__name__)











app = FastAPI(





    title="Troubleshooting Assistance API",





    description="API for industrial troubleshooting assistance",





    version="1.0.0"





)

















from typing import Optional
from app.services.development_troubleshooting_orchestrator import DevelopmentTroubleshootingRequest

class TroubleshootingRequest(BaseModel):
    machine_name: str
    error_code: str | None = None
    symptom: str
    operating_condition: str | None = None
    previous_attempts: str | None = None

    # Optional explicit structured request.
    # Free text above is context only and is never converted into evidence facts.
    structured_assistance: Optional[DevelopmentTroubleshootingRequest] = None


















class DocumentProcessingRequest(BaseModel):





    stored_filename: str

















class DocumentChunkingRequest(BaseModel):





    processed_filename: str





    chunk_words: int = Field(default=180, ge=80, le=400)





    overlap_words: int = Field(default=30, ge=0)

















class DocumentSearchRequest(BaseModel):





    model_config = ConfigDict(extra="forbid")











    vector_store_filename: str = Field(





        min_length=5,





        max_length=255,





        strict=True,





        pattern=r"^[^/\\:\x00]+\.[nN][pP][zZ]$",





        description="The .npz filename inside data/vector_store, not a folder path."





    )





    query: str = Field(





        default="",





        max_length=4000,





        strict=True,





        description="Question for semantic search. Ignored when alarm_number is supplied."





    )





    alarm_number: str | None = Field(





        default=None,





        strict=True,





        pattern=r"^[0-9]{1,8}$",





        description="Exact alarm number as a string, for example 1001. Use null for semantic search."





    )





    top_k: int = Field(default=5, ge=1, le=10, strict=True)











    plant_id: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    department: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    equipment_id: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    equipment_type: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    manufacturer: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    model: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    document_family_id: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    document_type: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    revision: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    document_status: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    @model_validator(mode="after")





    def require_search_input(self):





        self.query = self.query.strip()





        if self.alarm_number is None and not self.query:





            raise ValueError("Provide a nonempty query or an explicit alarm_number.")





        return self


















class EnterpriseDocumentSearchRequest(BaseModel):
    """
    Development request for registry-driven enterprise search.

    vector_store_filename is intentionally absent:
    vector artifacts are discovered through the enterprise
    registry.

    access_level is intentionally absent:
    caller-supplied metadata is not authorization.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    query: str = Field(
        default="",
        max_length=4000,
        strict=True,
        description=(
            "Question for enterprise semantic search. "
            "Ignored when alarm_number is supplied."
        ),
    )

    alarm_number: str | None = Field(
        default=None,
        strict=True,
        pattern=r"^[0-9]{1,8}$",
        description=(
            "Exact alarm number. Use null for "
            "enterprise semantic search."
        ),
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        strict=True,
    )

    plant_id: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    department: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    equipment_id: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    equipment_type: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    manufacturer: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    model: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    document_family_id: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    document_type: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    revision: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    document_status: str | None = Field(
        default=None,
        max_length=255,
        strict=True,
    )

    @model_validator(mode="after")
    def require_enterprise_search_input(self):

        self.query = self.query.strip()

        if (
            self.alarm_number is None
            and not self.query
        ):
            raise ValueError(
                "Provide a nonempty query or "
                "an explicit alarm_number."
            )

        return self


class ABBSearchRequest(BaseModel):





    model_config = ConfigDict(extra="forbid")











    vector_store_filename: str = Field(





        min_length=5,





        max_length=255,





        strict=True,





        pattern=r"^[^/\\:\x00]+\.[nN][pP][zZ]$",





        description="The reviewed ABB .npz filename inside data/vector_store."





    )





    query: str = Field(min_length=1, max_length=4000, strict=True)





    top_k: int = Field(default=5, ge=1, le=10, strict=True)











    @model_validator(mode="after")





    def normalize_query(self):





        self.query = self.query.strip()





        if not self.query:





            raise ValueError("Provide a nonempty ABB symptom query.")





        return self

















class ABBConfirmationRequest(BaseModel):





    model_config = ConfigDict(extra="forbid")











    vector_store_filename: str = Field(





        min_length=5,





        max_length=255,





        strict=True,





        pattern=r"^[^/\\:\x00]+\.[nN][pP][zZ]$",





        description="The reviewed ABB .npz filename inside data/vector_store."





    )





    symptom_id: str = Field(min_length=1, max_length=255, strict=True)





    top_k: int = Field(default=10, ge=1, le=10, strict=True)











    @model_validator(mode="after")





    def normalize_symptom_id(self):





        self.symptom_id = self.symptom_id.strip()





        if not self.symptom_id or any(





            ord(character) < 32 for character in self.symptom_id





        ):





            raise ValueError("Provide a valid ABB symptom_id.")





        return self

















@app.get("/")





def home():





    return {





        "project": (





            "Troubleshooting Assistance Through "





            "Expert Knowledge Retrieval Techniques"





        ),





        "message": "Backend is running successfully",





        "status": "active"





    }

















@app.get("/health")





def health_check():





    return {





        "status": "healthy",





        "service": "troubleshooting-assistant-api"





    }

















@app.post("/troubleshoot")
def troubleshoot(request: TroubleshootingRequest):
    """Main troubleshooting entry point with explicit evidence-scope routing.

    General free-text context is accepted for compatibility but is not used to
    infer manufacturer policy, alarm scope, observations, or diagnosis.
    """

    context = {
        "machine_name": request.machine_name,
        "error_code": request.error_code,
        "symptom": request.symptom,
        "operating_condition": request.operating_condition,
        "previous_attempts": request.previous_attempts,
    }

    if request.structured_assistance is None:
        from app.services.troubleshooting_input_guidance import (
            get_troubleshooting_input_guidance,
        )

        guidance = get_troubleshooting_input_guidance()

        return {
            "status": "needs_structured_input",
            "context": context,
            "supported_structured_modes": guidance[
                "supported_modes"
            ],
            "structured_input_guidance": guidance[
                "modes"
            ],
            "guidance_endpoint": (
                "/development/troubleshoot/guidance"
            ),
            "diagnosis_confirmed": False,
            "approved_for_automatic_execution": False,
            "development_only": True,
            "message": (
                "General troubleshooting context was received, but no "
                "evidence-scoped assistance request was supplied. "
                "Free text is not converted into condition facts or alarm scope."
            ),
        }


    try:
        from pydantic import TypeAdapter, ValidationError

        from app.services.development_troubleshooting_orchestrator import (
            DevelopmentTroubleshootingRequest,
            orchestrate_development_troubleshooting,
        )

        try:
            structured_request = TypeAdapter(
                DevelopmentTroubleshootingRequest
            ).validate_python(
                request.structured_assistance
            )
        except ValidationError as error:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Invalid structured_assistance payload: "
                    + str(error)
                ),
            ) from error

        assistance = orchestrate_development_troubleshooting(
            structured_request
        )

        return {
            "status": "assistance_returned",
            "context": context,
            "assistance": assistance,
            "diagnosis_confirmed": False,
            "approved_for_automatic_execution": False,
            "development_only": True,
            "message": (
                "Explicit structured assistance was processed by a "
                "development-validated evidence policy."
            ),
        }

    except HTTPException:
        raise

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Required prepared evidence source was not found.",
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception(
            "Main troubleshooting orchestration failed."
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Troubleshooting orchestration failed. "
                "Check the backend terminal for details."
            ),
        ) from error


















@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    plant_id: str | None = Form(None),
    department: str | None = Form(None),
    equipment_id: str | None = Form(None),
    equipment_type: str | None = Form(None),
    manufacturer: str | None = Form(None),
    model: str | None = Form(None),
    document_family_id: str | None = Form(None),
    supersedes_document_id: str | None = Form(None),
    document_type: str | None = Form(None),
    revision: str | None = Form(None),
    effective_date: str | None = Form(None),
    document_status: str | None = Form(None),
    access_level: str | None = Form(None),
):
    """
    Upload an expert-knowledge document and register its enterprise metadata.

    Enterprise metadata remains optional so existing file-only uploads continue
    to work. Missing metadata is stored as unknown rather than inferred.
    """

    document_information = await save_uploaded_document(file)

    try:
        relationship = analyze_enterprise_document_relationship(
            document_information,
            document_family_id=document_family_id,
            supersedes_document_id=supersedes_document_id,
        )

        registry_record = register_enterprise_document(
            document_information,
            plant_id=plant_id,
            department=department,
            equipment_id=equipment_id,
            equipment_type=equipment_type,
            manufacturer=manufacturer,
            model=model,
            document_family_id=document_family_id,
            supersedes_document_id=supersedes_document_id,
            document_type=document_type,
            revision=revision,
            effective_date=effective_date,
            document_status=document_status,
            access_level=access_level,
        )

    except ValueError as error:
        Path(
            document_information["saved_location"]
        ).unlink(missing_ok=True)

        raise HTTPException(
            status_code=422,
            detail=f"Document registry validation failed: {error}",
        ) from error

    except Exception as error:
        Path(
            document_information["saved_location"]
        ).unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail="Document registry update failed.",
        ) from error

    return {
        "status": "success",
        "message": "Expert knowledge document uploaded successfully",
        "document": document_information,
        "registry": registry_record,
        "relationship": relationship,
    }


@app.post("/documents/process")





def process_document(request: DocumentProcessingRequest):





    processing_result = process_pdf_document(





        stored_filename=request.stored_filename





    )











    return {





        "status": "success",





        "message": "PDF text extracted and saved successfully",





        "document": processing_result





    }

















@app.post("/documents/chunk")





def chunk_document(request: DocumentChunkingRequest):





    try:





        chunking_result = chunk_processed_document(





            processed_filename=request.processed_filename,





            chunk_words=request.chunk_words,





            overlap_words=request.overlap_words





        )











    except FileNotFoundError as error:





        raise HTTPException(





            status_code=404,





            detail=str(error)





        ) from error











    except FileExistsError as error:





        raise HTTPException(





            status_code=409,





            detail=(





                "A chunk file already exists for this document. "





                "Check data/chunked_documents before processing it again."





            )





        ) from error











    except ValueError as error:





        raise HTTPException(





            status_code=422,





            detail=str(error)





        ) from error











    except OSError as error:





        raise HTTPException(





            status_code=500,





            detail=(





                "Unable to read or save the chunk files. "





                "Check folder permissions and available disk space."





            )





        ) from error











    return {





        "status": "success",





        "message": "Document sections and searchable chunks saved successfully",





        "document": chunking_result





    }


















@app.post(
    "/development/documents/search/enterprise",
    tags=["Development"],
    summary=(
        "Search registered enterprise documents "
        "without selecting a vector-store filename"
    ),
    description=(
        "Discovers registered enterprise vector artifacts "
        "from explicit document metadata and searches across "
        "eligible single-artifact documents. Documents with "
        "multiple vector artifacts are withheld rather than "
        "auto-selected. This bounded development bridge uses a trusted process-level vector retrieval backend "
        "does not implement access authorization and does not "
        "claim production-scale 30k-document retrieval."
    ),
)
def search_enterprise_documents(
    request: EnterpriseDocumentSearchRequest,
):

    try:

        return retrieve_enterprise_sections_configured(
            query=request.query,
            alarm_number=request.alarm_number,
            top_k=request.top_k,
            metadata_filters={
                "plant_id":
                    request.plant_id,

                "department":
                    request.department,

                "equipment_id":
                    request.equipment_id,

                "equipment_type":
                    request.equipment_type,

                "manufacturer":
                    request.manufacturer,

                "model":
                    request.model,

                "document_family_id":
                    request.document_family_id,

                "document_type":
                    request.document_type,

                "revision":
                    request.revision,

                "document_status":
                    request.document_status,
            },
        )

    except FileNotFoundError as error:

        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except ValueError as error:

        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except Exception as error:

        logger.exception(
            "Enterprise document search failed."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Enterprise search could not be completed. "
                "Check the backend terminal for details."
            ),
        ) from error


@app.post(





    "/documents/search",





    summary="Retrieve manual sections by alarm number or question",





    description=(





        "Provide alarm_number for exact lookup, or query with alarm_number=null "





        "for semantic search. An explicit alarm number takes precedence over query. "





        "Unknown alarm numbers return not_found without semantic fallback. "





        "Semantic results are source candidates, not verified diagnoses; "





        "similarity is not confidence."





    )





)





def search_documents(request: DocumentSearchRequest):





    try:





        return retrieve_sections(





            vector_store_filename=request.vector_store_filename,





            query=request.query,





            alarm_number=request.alarm_number,





            top_k=request.top_k,
            metadata_filters={
                "plant_id": request.plant_id,
                "department": request.department,
                "equipment_id": request.equipment_id,
                "equipment_type": request.equipment_type,
                "manufacturer": request.manufacturer,
                "model": request.model,
                "document_family_id": request.document_family_id,
                "document_type": request.document_type,
                "revision": request.revision,
                "document_status": request.document_status,
            }





        )











    except FileNotFoundError as error:





        raise HTTPException(status_code=404, detail=str(error)) from error











    except ValueError as error:





        raise HTTPException(status_code=422, detail=str(error)) from error











    except Exception as error:





        logger.exception("Document search failed.")





        raise HTTPException(





            status_code=500,





            detail="Search could not be completed. Check the backend terminal for details."





        ) from error

















@app.post(





    "/documents/search/abb",





    summary="Route an ABB motor symptom to reviewed source records",





    description=(





        "Returns manufacturer source records for a clear symptom. When leading "





        "symptoms are too close, returns needs_clarification and withholds causes "





        "and guidance. Scores are ranking signals, not diagnostic confidence."





    )





)





def search_abb_documents(request: ABBSearchRequest):





    try:





        return retrieve_abb_records(





            vector_store_filename=request.vector_store_filename,





            query=request.query,





            top_k=request.top_k,





        )





    except FileNotFoundError as error:





        raise HTTPException(status_code=404, detail=str(error)) from error





    except ValueError as error:





        raise HTTPException(status_code=422, detail=str(error)) from error





    except Exception as error:





        logger.exception("ABB document search failed.")





        raise HTTPException(





            status_code=500,





            detail="ABB search could not be completed. Check the backend terminal for details."





        ) from error

















@app.post(





    "/documents/search/abb/confirm",





    summary="Retrieve one technician-confirmed ABB symptom group",





    description=(





        "Uses an exact symptom_id returned by ABB search. No semantic fallback "





        "is used. Manufacturer records are not confirmed diagnoses and are not "





        "approved for automatic execution."





    )





)





def confirm_abb_symptom(request: ABBConfirmationRequest):





    try:





        return retrieve_confirmed_abb_symptom(





            vector_store_filename=request.vector_store_filename,





            symptom_id=request.symptom_id,





            top_k=request.top_k,





        )





    except FileNotFoundError as error:





        raise HTTPException(status_code=404, detail=str(error)) from error





    except ValueError as error:





        raise HTTPException(status_code=422, detail=str(error)) from error





    except Exception as error:





        logger.exception("ABB symptom confirmation failed.")





        raise HTTPException(





            status_code=500,





            detail="ABB confirmation could not be completed. Check the backend terminal for details."





        ) from error

















# Development-only condition endpoint; no diagnosis or action approval.





from typing import Literal





from pydantic import StrictBool





from app.services.abb_condition_service import check_abb_pilot_condition

















class ABBPilotObservations(BaseModel):





    model_config = ConfigDict(extra="forbid")





    low_voltage_reported: list[StrictBool | None] = Field(





        default_factory=list, max_length=32,





        description="Reports for the same machine and interval: true, false, or null."





    )

















class ABBPilotConditionRequest(BaseModel):





    model_config = ConfigDict(extra="forbid")





    index_filename: str = Field(





        min_length=6, max_length=255, strict=True,





        pattern=r"^[^/\\:\x00-\x1f]+\.[jJ][sS][oO][nN]$",





        description="Evidence-index JSON filename inside data/condition_evidence."





    )





    record_id: Literal[





        "dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022_r013"





    ]





    observations: ABBPilotObservations











    @model_validator(mode="after")





    def validate_index_filename(self):





        if self.index_filename != self.index_filename.strip():





            raise ValueError("Do not include surrounding whitespace in the filename.")





        return self

















@app.post(





    "/development/abb/conditions/check",





    tags=["Development"],





    summary="Check the unreviewed ABB low-voltage pilot condition",





    description=(





        "Only Motor stalls / Low voltage (r013) is mapped. Checks explicit "





        "structured reports against this development condition. Missing or "





        "conflicting reports produce unknown. Does not interpret measurements, "





        "confirm a diagnosis, return remedies, or approve actions. No model call."





    ),





)





def check_abb_condition(request: ABBPilotConditionRequest):





    try:





        return check_abb_pilot_condition(





            index_filename=request.index_filename,





            record_id=request.record_id,





            observations=request.observations.model_dump(),





        )





    except FileNotFoundError as error:





        raise HTTPException(





            status_code=404, detail="Evidence index or prepared source file was not found."





        ) from error





    except ValueError as error:





        raise HTTPException(status_code=422, detail=str(error)) from error





    except Exception as error:





        logger.exception("ABB development condition check failed.")





        raise HTTPException(





            status_code=500,





            detail="Condition check could not be completed. Check the backend terminal for details."





        ) from error









from app.services.abb_stall_api import router as abb_stall_router




app.include_router(abb_stall_router)







from app.services.abb_stall_clarification_api import router as abb_stall_clarification_router



app.include_router(abb_stall_clarification_router)





from app.services.abb_stall_assistance import router as abb_stall_assistance_router


app.include_router(abb_stall_assistance_router)



from app.services.siemens_license_assistance import router as siemens_license_router

app.include_router(siemens_license_router)

from app.services.siemens_logfile_answer import router as siemens_logfile_answer_router
app.include_router(siemens_logfile_answer_router)

from app.services.development_troubleshooting_orchestrator import router as development_troubleshooting_router
app.include_router(development_troubleshooting_router)

from app.services.troubleshooting_input_guidance import router as troubleshooting_input_guidance_router
app.include_router(troubleshooting_input_guidance_router)

from app.services.troubleshooting_question_builder import router as troubleshooting_question_router
app.include_router(troubleshooting_question_router)

from app.services.troubleshooting_answer_builder import router as troubleshooting_answer_builder_router
app.include_router(troubleshooting_answer_builder_router)

from app.services.troubleshooting_turn_workflow import router as troubleshooting_turn_router
from app.services.assistant_workflow import router as assistant_workflow_router
app.include_router(troubleshooting_turn_router)
app.include_router(assistant_workflow_router)

# Development preview for the technician-oriented Frontend V2.
from app.services.frontend_v2_api import router as frontend_v2_router
app.include_router(frontend_v2_router)

