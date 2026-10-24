from typing import List, Dict, Any
from pydantic import BaseModel

class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    workspace_id: str
    text: str
    provenance: Dict[str, Any]

def chunk_document(document_id: str, workspace_id: str, file_type: str, content: Dict[str, Any]) -> List[Chunk]:
    chunks = []
    
    if file_type in [".pdf", "pdf"]:
        pages = content.get("pages", [])
        for p in pages:
            page_num = p.get("page")
            text = p.get("text", "")
            tables = p.get("tables", [])
            
            # Chunk page text if present
            if text.strip():
                chunks.append(Chunk(
                    chunk_id=f"{document_id}_p{page_num}_text",
                    document_id=document_id,
                    workspace_id=workspace_id,
                    text=text,
                    provenance={"source_type": "pdf", "page": page_num}
                ))
            
            # Chunk tables if present
            for idx, table in enumerate(tables):
                # extract_pdf_text yields tables as list[list[list[str]]]:
                # a list of row lists, each row a list of cell strings.
                table_str = "\n".join("\t".join(row) for row in table)
                if table_str.strip():
                    chunks.append(Chunk(
                        chunk_id=f"{document_id}_p{page_num}_table_{idx}",
                        document_id=document_id,
                        workspace_id=workspace_id,
                        text=f"Table {idx} on page {page_num}:\n{table_str}",
                        provenance={"source_type": "pdf_table", "page": page_num, "table_index": idx}
                    ))

    elif file_type in [".xlsx", ".xls", "excel"]:
        sheets = content.get("sheets", [])
        # Group cells by sheet for coherent chunks
        sheet_map: Dict[str, list] = {}
        for cell_item in content.get("cells", []):
            s_name = cell_item.get("sheet", "Sheet1")
            sheet_map.setdefault(s_name, []).append(cell_item)
            
        for s_name, cells in sheet_map.items():
            cell_lines = [f"{c.get('cell')}: {c.get('value')}" for c in cells]
            chunks.append(Chunk(
                chunk_id=f"{document_id}_sheet_{s_name}",
                document_id=document_id,
                workspace_id=workspace_id,
                text=f"Spreadsheet Sheet: {s_name}\n" + "\n".join(cell_lines),
                provenance={"source_type": "excel", "sheet": s_name}
            ))

    elif file_type in [".docx", "docx"]:
        paragraphs = content.get("paragraphs", [])
        text_block = "\n".join([p.get("text", "") for p in paragraphs if p.get("text")])
        if text_block.strip():
            chunks.append(Chunk(
                chunk_id=f"{document_id}_docx_body",
                document_id=document_id,
                workspace_id=workspace_id,
                text=text_block,
                provenance={"source_type": "docx"}
            ))

    elif file_type in [".csv", "csv"]:
        rows = content.get("rows", [])
        # extract_csv yields {"row": int, "values": [...]} per line.
        row_lines = [
            f"Row {r.get('row')}: " + ", ".join(r.get("values", []) or [])
            for r in rows
        ]
        csv_text = "\n".join(row_lines)
        if csv_text.strip():
            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}_csv_data",
                    document_id=document_id,
                    workspace_id=workspace_id,
                    text=csv_text,
                    provenance={"source_type": "csv"}
                )
            )

    return chunks