# backend/routers/admin.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
import json
import os

from database import get_session
from models import (
    Application,
    ApplicationDependency,
    ApplicationPurpose,
    ApplicationSymptom,
    ClassificationConfig
)
from schemas import (
    ApplicationCreate,
    ApplicationResponse,
    PurposeCreate,
    SymptomCreate,
    DependencyCreate,
    DependencyResponse,
)
from services.embedder import TextEmbedder
from security import require_operator, CurrentUser

router = APIRouter()
embedder = TextEmbedder()

# =====================================================================
# APPLICATIONS CRUD
# =====================================================================

@router.get("/applications", response_model=list[ApplicationResponse])
def get_all_apps(session: Session = Depends(get_session)):
    return session.exec(select(Application)).all()


@router.get("/applications/{app_id}", response_model=ApplicationResponse)
def get_one_app(app_id: int, session: Session = Depends(get_session)):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return app


@router.post("/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_app(request: ApplicationCreate, session: Session = Depends(get_session), current_user: CurrentUser = Depends(require_operator)):
    existing = session.exec(select(Application).where(Application.name == request.name)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exists")
    
    app = Application(name=request.name, description=request.description, owning_team=request.owning_team, contact=request.contact)
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


@router.put("/applications/{app_id}", response_model=ApplicationResponse)
def update_app(app_id: int, request: ApplicationCreate, session: Session = Depends(get_session), current_user: CurrentUser = Depends(require_operator)):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    
    app.name = request.name
    app.description = request.description
    app.owning_team = request.owning_team
    app.contact = request.contact
    session.commit()
    session.refresh(app)
    return app


@router.delete("/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app(app_id: int, session: Session = Depends(get_session), current_user: CurrentUser = Depends(require_operator)):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    session.delete(app)
    session.commit()


# =====================================================================
# PURPOSES & SYMPTOMS MANAGEMENT
# =====================================================================

@router.post("/applications/{app_id}/purposes", status_code=status.HTTP_201_CREATED)
def add_purpose(app_id: int, request: PurposeCreate, session: Session = Depends(get_session), current_user: CurrentUser = Depends(require_operator)):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    
    purpose = ApplicationPurpose(
        application_id=app_id,
        purpose_text=request.purpose_text,
        embedding=embedder.get_embedding(request.purpose_text)
    )
    session.add(purpose)
    session.commit()
    return {"message": "Added"}


@router.post("/applications/{app_id}/symptoms", status_code=status.HTTP_201_CREATED)
def add_symptom(app_id: int, request: SymptomCreate, session: Session = Depends(get_session), current_user: CurrentUser = Depends(require_operator)):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    
    symptom = ApplicationSymptom(
        application_id=app_id,
        symptom_text=request.symptom_text,
        embedding=embedder.get_embedding(request.symptom_text)
    )
    session.add(symptom)
    session.commit()
    return {"message": "Added"}


# =====================================================================
# DEPENDENCIES CRUD
# =====================================================================

@router.get("/dependencies", response_model=list[DependencyResponse])
def get_all_deps(session: Session = Depends(get_session)):
    return session.exec(select(ApplicationDependency)).all()


@router.post("/dependencies", response_model=DependencyResponse, status_code=status.HTTP_201_CREATED)
def create_dependency(request: DependencyCreate, session: Session = Depends(get_session), current_user: CurrentUser = Depends(require_operator)):
    if request.source_app_id == request.dependent_app_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Same app")
    
    dep = ApplicationDependency(
        source_app_id=request.source_app_id,
        dependent_app_id=request.dependent_app_id,
        dependency_nature=request.dependency_nature
    )
    session.add(dep)
    session.commit()
    session.refresh(dep)
    return dep


@router.delete("/dependencies/{dep_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dependency(dep_id: int, session: Session = Depends(get_session), current_user: CurrentUser = Depends(require_operator)):
    dep = session.get(ApplicationDependency, dep_id)
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    session.delete(dep)
    session.commit()


# =====================================================================
# SEEDING DATA
# =====================================================================

@router.post("/seed", status_code=status.HTTP_200_OK)
def seed_database(data: dict, session: Session = Depends(get_session)):
    try:
            
        for app_data in data.get("applications", []):
            existing = session.exec(select(Application).where(Application.name == app_data["name"])).first()
            if not existing:
                app = Application(id=app_data["id"], name=app_data["name"], description=app_data["description"], owning_team=app_data["owning_team"], contact=app_data["contact"])
                session.add(app)
        session.commit()

        for purp_data in data.get("application_purposes", []):
            existing = session.exec(select(ApplicationPurpose).where(ApplicationPurpose.application_id == purp_data["application_id"], ApplicationPurpose.purpose_text == purp_data["purpose_text"])).first()
            if not existing:
                purpose = ApplicationPurpose(application_id=purp_data["application_id"], purpose_text=purp_data["purpose_text"], embedding=embedder.get_embedding(purp_data["purpose_text"]))
                session.add(purpose)

        for sym_data in data.get("application_symptoms", []):
            existing = session.exec(select(ApplicationSymptom).where(ApplicationSymptom.application_id == sym_data["application_id"], ApplicationSymptom.symptom_text == sym_data["symptom_text"])).first()
            if not existing:
                symptom = ApplicationSymptom(application_id=sym_data["application_id"], symptom_text=sym_data["symptom_text"], embedding=embedder.get_embedding(sym_data["symptom_text"]))
                session.add(symptom)

        for cfg_data in data.get("classification_configs", []):
            existing = session.exec(select(ClassificationConfig).where(ClassificationConfig.category == cfg_data["category"], ClassificationConfig.label == cfg_data["label"])).first()
            if not existing:
                cfg = ClassificationConfig(category=cfg_data["category"], label=cfg_data["label"], description=cfg_data["description"])
                session.add(cfg)

        for dep_data in data.get("application_dependencies", []):
            existing = session.exec(select(ApplicationDependency).where(ApplicationDependency.source_app_id == dep_data["source_app_id"], ApplicationDependency.dependent_app_id == dep_data["dependent_app_id"])).first()
            if not existing:
                dep = ApplicationDependency(source_app_id=dep_data["source_app_id"], dependent_app_id=dep_data["dependent_app_id"], dependency_nature=dep_data["dependency_nature"])
                session.add(dep)
                
        session.commit()
        return {"status": "success"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
