import openpyxl

wb = openpyxl.load_workbook("../【生成AI】実施記録分析シート_20260610132229.xlsx", data_only=True)
ws = wb["実施記録シート"]

with open("scratch_first_rows.txt", "w", encoding="utf-8") as f:
    for row_idx in range(1, 11):
        row_values = [cell.value for cell in ws[row_idx]]
        f.write(f"Row {row_idx}: {row_values[:20]}\n")
print("First 10 rows written to scratch_first_rows.txt")
