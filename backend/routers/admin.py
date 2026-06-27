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
)
from schemas import (
    ApplicationCreate,
    ApplicationResponse,
    PurposeCreate,
    SymptomCreate,
    DependencyCreate,
    DependencyResponse,
)

router = APIRouter()


# =====================================================================
# APPLICATIONS CRUD
# =====================================================================

@router.get("/applications", response_model=list[ApplicationResponse])
def get_all_apps(session: Session = Depends(get_session)):
    """Retrieve all registered applications."""
    return session.exec(select(Application)).all()


@router.get("/applications/{app_id}", response_model=ApplicationResponse)
def get_one_app(app_id: int, session: Session = Depends(get_session)):
    """Retrieve details for a single application."""
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found"
        )
    return app


@router.post("/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_app(request: ApplicationCreate, session: Session = Depends(get_session)):
    """Register a new application."""
    existing = session.exec(
        select(Application).where(Application.name == request.name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"App '{request.name}' already exists"
        )
    
    app = Application(
        name=request.name,
        description=request.description,
        owning_team=request.owning_team,
        contact=request.contact
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


@router.put("/applications/{app_id}", response_model=ApplicationResponse)
def update_app(app_id: int, request: ApplicationCreate, session: Session = Depends(get_session)):
    """Update details of an existing application."""
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found"
        )
    
    app.name = request.name
    app.description = request.description
    app.owning_team = request.owning_team
    app.contact = request.contact

    session.commit()
    session.refresh(app)
    return app


@router.delete("/applications/{app_id}", status_code=status.HTTP_200_OK)
def delete_app(app_id: int, session: Session = Depends(get_session)):
    """Delete an application."""
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found"
        )
    session.delete(app)
    session.commit()
    return {"message": f"App {app_id} deleted"}


# =====================================================================
# PURPOSES & SYMPTOMS MANAGEMENT
# =====================================================================

@router.post("/applications/{app_id}/purposes", status_code=status.HTTP_201_CREATED)
def add_purpose(app_id: int, request: PurposeCreate, session: Session = Depends(get_session)):
    """Add a purpose description to an application (embedding will be generated)."""
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found"
        )
    
    # In a full flow, Team B's embedder will create the embedding.
    # Initially we save with a dummy vector until full integration.
    purpose = ApplicationPurpose(
        application_id=app_id,
        purpose_text=request.purpose_text,
        embedding=[0.0] * 768
    )
    session.add(purpose)
    session.commit()
    return {"message": "Application purpose added successfully"}


@router.post("/applications/{app_id}/symptoms", status_code=status.HTTP_201_CREATED)
def add_symptom(app_id: int, request: SymptomCreate, session: Session = Depends(get_session)):
    """Add a common symptom description to an application (embedding will be generated)."""
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found"
        )
    
    symptom = ApplicationSymptom(
        application_id=app_id,
        symptom_text=request.symptom_text,
        embedding=[0.0] * 768
    )
    session.add(symptom)
    session.commit()
    return {"message": "Application symptom added successfully"}


# =====================================================================
# DEPENDENCIES CRUD
# =====================================================================

@router.get("/dependencies", response_model=list[DependencyResponse])
def get_all_deps(session: Session = Depends(get_session)):
    """Retrieve all dependency mappings."""
    return session.exec(select(ApplicationDependency)).all()


@router.post("/dependencies", response_model=DependencyResponse, status_code=status.HTTP_201_CREATED)
def create_dependency(request: DependencyCreate, session: Session = Depends(get_session)):
    """Create a new dependency connection between two applications."""
    if request.source_app_id == request.dependent_app_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An application cannot depend on itself"
        )
    
    # Validate apps exist
    src_app = session.get(Application, request.source_app_id)
    target_app = session.get(Application, request.dependent_app_id)
    if not src_app or not target_app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both application IDs do not exist"
        )
    
    dep = ApplicationDependency(
        source_app_id=request.source_app_id,
        dependent_app_id=request.dependent_app_id,
        dependency_nature=request.dependency_nature
    )
    session.add(dep)
    session.commit()
    session.refresh(dep)
    return dep


@router.delete("/dependencies/{dep_id}", status_code=status.HTTP_200_OK)
def delete_dependency(dep_id: int, session: Session = Depends(get_session)):
    """Remove a dependency connection."""
    dep = session.get(ApplicationDependency, dep_id)
    if not dep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dependency connection {dep_id} not found"
        )
    session.delete(dep)
    session.commit()
    return {"message": "Dependency link deleted"}


# =====================================================================
# SEEDING DATA
# =====================================================================

@router.post("/seed", status_code=status.HTTP_200_OK)
def seed_database(session: Session = Depends(get_session)):
    """Seed the database registry using the dummy_seed_data.json file."""
    seed_file_path = "../dummy_seed_data.json"
    
    if not os.path.exists(seed_file_path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Seed file not found at {os.path.abspath(seed_file_path)}"
        )
        
    try:
        with open(seed_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # 1. Seed applications
        for app_data in data.get("applications", []):
            existing = session.exec(
                select(Application).where(Application.name == app_data["name"])
            ).first()
            if not existing:
                app = Application(
                    id=app_data["id"],
                    name=app_data["name"],
                    description=app_data["description"],
                    owning_team=app_data["owning_team"],
                    contact=app_data["contact"]
                )
                session.add(app)
        session.commit()

        # 2. Seed purposes (with dummy vector)
        for purp_data in data.get("application_purposes", []):
            existing = session.exec(
                select(ApplicationPurpose).where(
                    ApplicationPurpose.application_id == purp_data["application_id"],
                    ApplicationPurpose.purpose_text == purp_data["purpose_text"]
                )
            ).first()
            if not existing:
                purpose = ApplicationPurpose(
                    application_id=purp_data["application_id"],
                    purpose_text=purp_data["purpose_text"],
                    embedding=[0.0] * 768
                )
                session.add(purpose)

        # 3. Seed symptoms (with dummy vector)
        for sym_data in data.get("application_symptoms", []):
            existing = session.exec(
                select(ApplicationSymptom).where(
                    ApplicationSymptom.application_id == sym_data["application_id"],
                    ApplicationSymptom.symptom_text == sym_data["symptom_text"]
                )
            ).first()
            if not existing:
                symptom = ApplicationSymptom(
                    application_id=sym_data["application_id"],
                    symptom_text=sym_data["symptom_text"],
                    embedding=[0.0] * 768
                )
                session.add(symptom)

        # 4. Seed dependencies
        for dep_data in data.get("application_dependencies", []):
            existing = session.exec(
                select(ApplicationDependency).where(
                    ApplicationDependency.source_app_id == dep_data["source_app_id"],
                    ApplicationDependency.dependent_app_id == dep_data["dependent_app_id"]
                )
            ).first()
            if not existing:
                dep = ApplicationDependency(
                    source_app_id=dep_data["source_app_id"],
                    dependent_app_id=dep_data["dependent_app_id"],
                    dependency_nature=dep_data["dependency_nature"]
                )
                session.add(dep)
                
        session.commit()
        return {"status": "success", "message": "Database seeded from dummy_seed_data.json successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed database: {str(e)}"
        )