"""Order history endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.database import get_connection

router = APIRouter(tags=["orders"])


class Order(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    status: str


@router.get("/users/{user_id}/orders", response_model=list[Order])
def list_user_orders(user_id: int):
    with get_connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        rows = conn.execute(
            "SELECT o.id, o.product_id, p.name AS product_name, o.quantity, o.status "
            "FROM orders o JOIN products p ON p.id = o.product_id "
            "WHERE o.user_id = ? ORDER BY o.id",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]
