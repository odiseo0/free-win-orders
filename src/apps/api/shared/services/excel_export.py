class ExcelExportService:
    async def export_order(self, order_id: str) -> str:
        return f"order-{order_id}.xlsx"
