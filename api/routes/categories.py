from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db, DocumentCategory

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    parent_id: UUID | None = None
    icon: str | None = None
    color: str | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_id: UUID | None = None
    icon: str | None = None
    color: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class CategoryResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    parent_id: UUID | None
    icon: str | None
    color: str | None
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True


class CategoryTreeResponse(CategoryResponse):
    children: list["CategoryTreeResponse"] = []


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all document categories."""
    query = select(DocumentCategory).order_by(
        DocumentCategory.sort_order,
        DocumentCategory.name,
    )

    if active_only:
        query = query.where(DocumentCategory.is_active == True)

    result = await db.execute(query)
    categories = result.scalars().all()

    return [CategoryResponse.model_validate(c) for c in categories]


@router.get("/tree", response_model=list[CategoryTreeResponse])
async def get_category_tree(
    db: AsyncSession = Depends(get_db),
):
    """Get categories as a hierarchical tree."""
    query = select(DocumentCategory).where(
        DocumentCategory.is_active == True
    ).order_by(DocumentCategory.sort_order, DocumentCategory.name)

    result = await db.execute(query)
    categories = result.scalars().all()

    # Build tree
    category_map = {c.id: CategoryTreeResponse.model_validate(c) for c in categories}

    root_categories = []
    for cat in categories:
        cat_response = category_map[cat.id]
        if cat.parent_id and cat.parent_id in category_map:
            category_map[cat.parent_id].children.append(cat_response)
        else:
            root_categories.append(cat_response)

    return root_categories


@router.post("", response_model=CategoryResponse)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new document category."""
    # Check code uniqueness
    existing = await db.execute(
        select(DocumentCategory).where(DocumentCategory.code == data.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Category code '{data.code}' already exists")

    # Validate parent exists
    if data.parent_id:
        parent = await db.execute(
            select(DocumentCategory).where(DocumentCategory.id == data.parent_id)
        )
        if not parent.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Parent category not found")

    category = DocumentCategory(
        code=data.code,
        name=data.name,
        description=data.description,
        parent_id=data.parent_id,
        icon=data.icon,
        color=data.color,
        sort_order=data.sort_order,
    )

    db.add(category)
    await db.commit()
    await db.refresh(category)

    return CategoryResponse.model_validate(category)


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single category."""
    query = select(DocumentCategory).where(DocumentCategory.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    return CategoryResponse.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a category."""
    query = select(DocumentCategory).where(DocumentCategory.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if data.name is not None:
        category.name = data.name
    if data.description is not None:
        category.description = data.description
    if data.parent_id is not None:
        # Prevent circular reference
        if data.parent_id == category_id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent")
        category.parent_id = data.parent_id
    if data.icon is not None:
        category.icon = data.icon
    if data.color is not None:
        category.color = data.color
    if data.is_active is not None:
        category.is_active = data.is_active
    if data.sort_order is not None:
        category.sort_order = data.sort_order

    await db.commit()
    await db.refresh(category)

    return CategoryResponse.model_validate(category)


@router.delete("/{category_id}")
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a category."""
    query = select(DocumentCategory).where(DocumentCategory.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    await db.delete(category)
    await db.commit()

    return {"message": "Category deleted"}


@router.post("/seed-defaults")
async def seed_default_categories(
    db: AsyncSession = Depends(get_db),
):
    """Seed database with default Chilean document categories."""
    defaults = [
        {"code": "dte", "name": "Documentos Tributarios", "icon": "file-text", "color": "#3b82f6", "sort_order": 0},
        {"code": "boleta", "name": "Boleta Electrónica", "parent_code": "dte", "icon": "receipt", "color": "#22c55e", "sort_order": 1},
        {"code": "factura", "name": "Factura Electrónica", "parent_code": "dte", "icon": "file-invoice", "color": "#f59e0b", "sort_order": 2},
        {"code": "guia_despacho", "name": "Guía de Despacho", "parent_code": "dte", "icon": "truck", "color": "#8b5cf6", "sort_order": 3},
        {"code": "nota_credito", "name": "Nota de Crédito", "parent_code": "dte", "icon": "file-minus", "color": "#ef4444", "sort_order": 4},
        {"code": "nota_debito", "name": "Nota de Débito", "parent_code": "dte", "icon": "file-plus", "color": "#ec4899", "sort_order": 5},
        {"code": "contratos", "name": "Contratos", "icon": "file-signature", "color": "#6366f1", "sort_order": 10},
        {"code": "identificacion", "name": "Identificación", "icon": "id-card", "color": "#14b8a6", "sort_order": 20},
        {"code": "otro", "name": "Otros", "icon": "file", "color": "#64748b", "sort_order": 99},
    ]

    created = []
    parent_map = {}

    # First pass: create root categories
    for cat_data in defaults:
        if "parent_code" in cat_data:
            continue

        existing = await db.execute(
            select(DocumentCategory).where(DocumentCategory.code == cat_data["code"])
        )
        if existing.scalar_one_or_none():
            # Get existing for parent mapping
            result = await db.execute(
                select(DocumentCategory).where(DocumentCategory.code == cat_data["code"])
            )
            parent_map[cat_data["code"]] = result.scalar_one().id
            continue

        category = DocumentCategory(
            code=cat_data["code"],
            name=cat_data["name"],
            icon=cat_data.get("icon"),
            color=cat_data.get("color"),
            sort_order=cat_data.get("sort_order", 0),
        )
        db.add(category)
        await db.flush()
        parent_map[cat_data["code"]] = category.id
        created.append(cat_data["code"])

    # Second pass: create child categories
    for cat_data in defaults:
        if "parent_code" not in cat_data:
            continue

        existing = await db.execute(
            select(DocumentCategory).where(DocumentCategory.code == cat_data["code"])
        )
        if existing.scalar_one_or_none():
            continue

        parent_id = parent_map.get(cat_data["parent_code"])

        category = DocumentCategory(
            code=cat_data["code"],
            name=cat_data["name"],
            parent_id=parent_id,
            icon=cat_data.get("icon"),
            color=cat_data.get("color"),
            sort_order=cat_data.get("sort_order", 0),
        )
        db.add(category)
        created.append(cat_data["code"])

    await db.commit()

    return {"message": f"Created {len(created)} categories", "categories": created}
