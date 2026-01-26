from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas.template import (
    TemplateCreate,
    TemplateDetailResponse,
    TemplateFieldCreate,
    TemplateFieldResponse,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from models import get_db, ExtractionTemplate, TemplateField, DocumentType, FieldType

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    doc_type: DocumentType | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all extraction templates."""
    query = select(ExtractionTemplate).order_by(
        ExtractionTemplate.priority.desc(),
        ExtractionTemplate.name,
    )

    if doc_type:
        query = query.where(ExtractionTemplate.doc_type == doc_type)
    if active_only:
        query = query.where(ExtractionTemplate.is_active == True)

    result = await db.execute(query)
    templates = result.scalars().all()

    return TemplateListResponse(
        items=[TemplateResponse.model_validate(t) for t in templates],
        total=len(templates),
    )


@router.post("", response_model=TemplateDetailResponse)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new extraction template with fields."""
    # Check code uniqueness
    existing = await db.execute(
        select(ExtractionTemplate).where(ExtractionTemplate.code == data.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Template code '{data.code}' already exists")

    template = ExtractionTemplate(
        name=data.name,
        code=data.code,
        description=data.description,
        doc_type=data.doc_type,
        is_active=data.is_active,
        priority=data.priority,
        classification_keywords=data.classification_keywords,
    )

    for i, field_data in enumerate(data.fields):
        field = TemplateField(
            name=field_data.name,
            label=field_data.label,
            field_type=field_data.field_type,
            pattern=field_data.pattern,
            pattern_flags=field_data.pattern_flags,
            required=field_data.required,
            order=field_data.order or i,
            validation_rules=field_data.validation_rules,
            post_processing=field_data.post_processing,
        )
        template.fields.append(field)

    db.add(template)
    await db.commit()
    await db.refresh(template)

    # Reload with fields
    query = (
        select(ExtractionTemplate)
        .options(selectinload(ExtractionTemplate.fields))
        .where(ExtractionTemplate.id == template.id)
    )
    result = await db.execute(query)
    template = result.scalar_one()

    return TemplateDetailResponse.model_validate(template)


@router.get("/{template_id}", response_model=TemplateDetailResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a template with all its fields."""
    query = (
        select(ExtractionTemplate)
        .options(selectinload(ExtractionTemplate.fields))
        .where(ExtractionTemplate.id == template_id)
    )
    result = await db.execute(query)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateDetailResponse.model_validate(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update template metadata (not fields)."""
    query = select(ExtractionTemplate).where(ExtractionTemplate.id == template_id)
    result = await db.execute(query)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if data.name is not None:
        template.name = data.name
    if data.description is not None:
        template.description = data.description
    if data.is_active is not None:
        template.is_active = data.is_active
    if data.priority is not None:
        template.priority = data.priority
    if data.classification_keywords is not None:
        template.classification_keywords = data.classification_keywords

    await db.commit()
    await db.refresh(template)

    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a template and all its fields."""
    query = select(ExtractionTemplate).where(ExtractionTemplate.id == template_id)
    result = await db.execute(query)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.delete(template)
    await db.commit()

    return {"message": "Template deleted"}


# Field management

@router.post("/{template_id}/fields", response_model=TemplateFieldResponse)
async def add_field(
    template_id: UUID,
    data: TemplateFieldCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a field to a template."""
    query = select(ExtractionTemplate).where(ExtractionTemplate.id == template_id)
    result = await db.execute(query)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    field = TemplateField(
        template_id=template_id,
        name=data.name,
        label=data.label,
        field_type=data.field_type,
        pattern=data.pattern,
        pattern_flags=data.pattern_flags,
        required=data.required,
        order=data.order,
        validation_rules=data.validation_rules,
        post_processing=data.post_processing,
    )

    db.add(field)
    await db.commit()
    await db.refresh(field)

    return TemplateFieldResponse.model_validate(field)


@router.patch("/{template_id}/fields/{field_id}", response_model=TemplateFieldResponse)
async def update_field(
    template_id: UUID,
    field_id: UUID,
    data: TemplateFieldCreate,
    db: AsyncSession = Depends(get_db),
):
    """Update a template field."""
    query = select(TemplateField).where(
        TemplateField.id == field_id,
        TemplateField.template_id == template_id,
    )
    result = await db.execute(query)
    field = result.scalar_one_or_none()

    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    field.name = data.name
    field.label = data.label
    field.field_type = data.field_type
    field.pattern = data.pattern
    field.pattern_flags = data.pattern_flags
    field.required = data.required
    field.order = data.order
    field.validation_rules = data.validation_rules
    field.post_processing = data.post_processing

    await db.commit()
    await db.refresh(field)

    return TemplateFieldResponse.model_validate(field)


@router.delete("/{template_id}/fields/{field_id}")
async def delete_field(
    template_id: UUID,
    field_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a field from a template."""
    query = select(TemplateField).where(
        TemplateField.id == field_id,
        TemplateField.template_id == template_id,
    )
    result = await db.execute(query)
    field = result.scalar_one_or_none()

    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    await db.delete(field)
    await db.commit()

    return {"message": "Field deleted"}


@router.post("/seed-defaults")
async def seed_default_templates(
    db: AsyncSession = Depends(get_db),
):
    """Seed database with default extraction templates."""
    from core.extractor import DEFAULT_TEMPLATES

    created = []

    for code, template_data in DEFAULT_TEMPLATES.items():
        # Check if exists
        existing = await db.execute(
            select(ExtractionTemplate).where(ExtractionTemplate.code == code)
        )
        if existing.scalar_one_or_none():
            continue

        template = ExtractionTemplate(
            name=template_data["name"],
            code=template_data["code"],
            doc_type=DocumentType(template_data["doc_type"]),
            classification_keywords=template_data.get("classification_keywords", []),
            is_active=True,
            priority=10,
        )

        for i, field_data in enumerate(template_data.get("fields", [])):
            field = TemplateField(
                name=field_data["name"],
                label=field_data["label"],
                field_type=FieldType(field_data.get("field_type", "text")),
                pattern=field_data["pattern"],
                pattern_flags=field_data.get("pattern_flags", "IGNORECASE"),
                required=field_data.get("required", False),
                order=i,
                post_processing=field_data.get("post_processing"),
            )
            template.fields.append(field)

        db.add(template)
        created.append(code)

    await db.commit()

    return {"message": f"Created {len(created)} templates", "templates": created}
