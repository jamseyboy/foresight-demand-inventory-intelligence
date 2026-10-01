# This Page is a guide on how the columns structure should follow

Before running the src files make sure the raw files are named `sales_daily.csv`, `inventory_snapshots.csv`,`sku_master.csv`and `calendar.csv`

And the csv table has columns as below:

**sales_daily.csv**

| Date  | SKU  | Units_Sold | Revenue | Price | Promotion |
|-------|------|------------|---------|-------|-----------|
| ... . | .... | ....       | ....    | ....  | ....      |

**inventory_snapshots.csv**

| Snapshot_Date | SKU  | Current_Stock | On_Order | Lead_Time_Days | Safety_Stock | Reorder_Point | Inventory_Value |
|---------------|------|---------------|----------|----------------|--------------|---------------|-----------------|
| ...           | ...  | ...           | ...      | ...            | ...          | ...           | ...             |


**sku_master.csv**

| SKU | Product_Name | Category | Subcategory | Launch_Date | Cost_Price | Selling_Price | Gross_Margin_Per_Unit |
|-----|--------------|----------|-------------|-------------|------------|---------------|-----------------------|
| ... | ...          | ...      | ...         | ...         | ...        | ...           | ...                   |


**calendar.csv**

| date | year | month | quarter | week | day_of_week | is_weekend | season | holiday | is_holiday | promotion_event |
|------|------|-------|---------|------|-------------|------------|--------|---------|------------|-----------------|
| ...  | ...  | ...   | ...     | ...  | ...         | ...        | ...    | ...     | ...        | ...             |