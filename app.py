#!/usr/bin/env python3
import re
from flask import Flask, render_template, request, jsonify
import pymysql

app = Flask(__name__)

DB_CONFIG = {
    "host": "bioed-new.bu.edu",
    "user": "vgupta7",
    "password": "dRumsfab",
    "database": "Team14",
    "port": 4253
}

_GENE_RE = re.compile(r'^[A-Z0-9\-\.]+$')

def get_connection():
    return pymysql.connect(
        host=DB_CONFIG["host"], user=DB_CONFIG["user"],
        password=DB_CONFIG["password"], database=DB_CONFIG["database"],
        port=DB_CONFIG["port"], cursorclass=pymysql.cursors.Cursor
    )

def _safe_gene(g):
    g = (g or "").strip().upper()
    return g if _GENE_RE.match(g) else None

def _norm_ct(ct):
    """Normalize DB cell type names to display names (Roman → numeric suffixes)."""
    if ct == "Astro-I":   return "Astro-1"
    if ct == "Astro-II":  return "Astro-2"
    if ct == "Exc-I":     return "Exc-1"
    if ct == "Exc-II":    return "Exc-2"
    if ct == "Exc-III":   return "Exc-3"
    return ct

def _db_ct(ct):
    """Reverse: convert display names back to DB values for SQL WHERE clauses."""
    if ct == "Astro-1":  return "Astro-I"
    if ct == "Astro-2":  return "Astro-II"
    if ct == "Exc-1":    return "Exc-I"
    if ct == "Exc-2":    return "Exc-II"
    if ct == "Exc-3":    return "Exc-III"
    return ct

# ── Gene autocomplete ──────────────────────────────────────────────────────────
@app.route("/genes")
def genes():
    q = request.args.get("q", "").strip().upper()
    if len(q) < 2:
        return jsonify([])
    try:
        conn = get_connection()
        cur  = conn.cursor()
        # prefix-only — uses idx_gene, fast on 44M rows
        cur.execute(
            "SELECT DISTINCT gene FROM expression_sub WHERE gene LIKE %s ORDER BY gene LIMIT 20",
            (q + "%",)
        )
        results = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify(results[:15])
    except Exception:
        return jsonify([])

# ── All cells (for cell-type UMAP panels, no expression join) ─────────────────
@app.route("/cells")
def cells():
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT cell_id, Final_Cell_Type, APOE_Genotype, UMAP_1, UMAP_2
            FROM merged_cells WHERE UMAP_1 IS NOT NULL
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify([
            {"cell_id": r[0], "cell_type": _norm_ct(r[1]), "genotype": r[2],
             "umap1": float(r[3]), "umap2": float(r[4])}
            for r in rows
        ])
    except Exception as e:
        return jsonify({"error": str(e)})

# ── Index ──────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    cell_types, samples = [], []
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT DISTINCT Final_Cell_Type FROM merged_cells ORDER BY Final_Cell_Type")
        cell_types = [_norm_ct(r[0]) for r in cur.fetchall() if r[0]]
        cur.execute("SELECT DISTINCT dmm_ID FROM merged_cells ORDER BY dmm_ID")
        samples = [r[0] for r in cur.fetchall() if r[0]]
        cur.close(); conn.close()
    except Exception as e:
        print(f"Dropdown error: {e}")
    return render_template("index.html", cell_types=cell_types, samples=samples)

# ── UMAP / Violin / Dot / Scatter ──────────────────────────────────────────────
@app.route("/query", methods=["POST"])
def query():
    gene      = _safe_gene(request.form.get("gene", "APOE"))
    genotype  = request.form.getlist("genotype")
    plot_type = request.form.get("plot_type", "umap")
    cts       = [_db_ct(c) for c in request.form.getlist("cell_type")]
    samples = request.form.getlist("sample")

    if not gene:
        return jsonify({"error": "Invalid gene name"})

    try:
        conn = get_connection()
        cur  = conn.cursor()

        # ── UMAP ──────────────────────────────────────────────────────────────
        # Drive from expression_sub via idx_gene, then join tiny merged_cells.
        # Cells with 0 expression are excluded here; the /cells endpoint
        # provides all cells for the cell-type panels.
        if plot_type == "umap":
            clauses = ["mc.UMAP_1 IS NOT NULL", "ef.gene = %s"]
            params  = [gene]
            if genotype:
                clauses.append(f"mc.APOE_Genotype IN ({','.join(['%s']*len(genotype))})")
                params.extend(genotype)
            if cts:
                clauses.append(f"mc.Final_Cell_Type IN ({','.join(['%s']*len(cts))})")
                params.extend(cts)
            if samples and "All" not in samples:
                clauses.append(f"mc.dmm_ID IN ({','.join(['%s']*len(samples))})")
                params.extend(samples)
            w = "WHERE " + " AND ".join(clauses)
            cur.execute(f"""
                SELECT ef.value, mc.Final_Cell_Type,
                       mc.APOE_Genotype, mc.UMAP_1, mc.UMAP_2
                FROM expression_sub ef
                STRAIGHT_JOIN merged_cells mc ON mc.cell_id = ef.cell_id
                {w} LIMIT 10000
            """, params)
            rows = cur.fetchall()
            cur.close(); conn.close()
            return jsonify({"type": "umap", "data": [
                {"expr": float(r[0]), "cell_type": _norm_ct(r[1]), "genotype": r[2],
                 "umap1": r[3], "umap2": r[4]}
                for r in rows
            ]})

        # ── Violin ────────────────────────────────────────────────────────────
        # index-first from expression_sub
        elif plot_type == "violin":
            clauses = ["ef.gene = %s"]
            params  = [gene]
            if genotype:
                clauses.append(f"mc.APOE_Genotype IN ({','.join(['%s']*len(genotype))})")
                params.extend(genotype)
            if cts:
                clauses.append(f"mc.Final_Cell_Type IN ({','.join(['%s']*len(cts))})")
                params.extend(cts)
            w = "WHERE " + " AND ".join(clauses)
            cur.execute(f"""
                SELECT mc.APOE_Genotype, mc.Final_Cell_Type, ef.value
                FROM expression_sub ef
                STRAIGHT_JOIN merged_cells mc ON mc.cell_id = ef.cell_id
                {w}
                LIMIT 8000
            """, params)
            rows = cur.fetchall()
            cur.close(); conn.close()
            return jsonify({"type": "violin", "gene": gene, "data": [
                {"g": r[0], "ct": _norm_ct(r[1]), "v": float(r[2])} for r in rows
        ]})

        # ── Dot plot ──────────────────────────────────────────────────────────
        elif plot_type == "dot":
            clauses = []
            params  = [gene]  # for the subquery
            if genotype:
                clauses.append(f"mc.APOE_Genotype IN ({','.join(['%s']*len(genotype))})")
                params.extend(genotype)
            if cts:
                clauses.append(f"mc.Final_Cell_Type IN ({','.join(['%s']*len(cts))})")
                params.extend(cts)
            w = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            cur.execute(f"""
                SELECT mc.Final_Cell_Type, mc.APOE_Genotype,
                    AVG(COALESCE(ef.value, 0)),
                    COUNT(ef.cell_id) / COUNT(mc.cell_id)
                FROM merged_cells mc
                LEFT JOIN (SELECT cell_id, value FROM expression_sub WHERE gene = %s) ef
                    ON mc.cell_id = ef.cell_id
                {w}
                GROUP BY mc.Final_Cell_Type, mc.APOE_Genotype
            """, params)
            rows = cur.fetchall()
            cur.close(); conn.close()
            return jsonify({"type": "dot", "gene": gene, "data": [
                {"ct": _norm_ct(r[0]), "g": r[1], "avg": float(r[2] or 0), "pct": float(r[3] or 0)}
                for r in rows
        ]})

        # ── Scatter ───────────────────────────────────────────────────────────
        elif plot_type == "scatter":
            clauses = ["ef.gene = %s"]
            params  = [gene]
            if genotype:
                clauses.append(f"mc.APOE_Genotype IN ({','.join(['%s']*len(genotype))})")
                params.extend(genotype)
            if cts:
                clauses.append(f"mc.Final_Cell_Type IN ({','.join(['%s']*len(cts))})")
                params.extend(cts)
            w = "WHERE " + " AND ".join(clauses)
            cur.execute(f"""
                SELECT mc.Final_Cell_Type, mc.APOE_Genotype, ef.value
                FROM expression_sub ef
                STRAIGHT_JOIN merged_cells mc ON mc.cell_id = ef.cell_id
                {w}
                LIMIT 5000
            """, params)
            rows = cur.fetchall()
            cur.close(); conn.close()
            return jsonify({"type": "scatter", "gene": gene, "data": [
                {"cell_type": _norm_ct(r[0]), "genotype": r[1], "expr": float(r[2])} for r in rows
            ]})

        cur.close(); conn.close()
        return jsonify({"error": "Unknown plot type"})
    except Exception as e:
        return jsonify({"error": str(e)})

# ── Multi-gene (dot + heatmap) ─────────────────────────────────────────────────
@app.route("/multigene", methods=["POST"])
def multigene():
    raw_genes = request.form.getlist("genes[]")
    plot_type = request.form.get("plot_type", "dot")
    genotype  = request.form.getlist("genotype")
    cts       = [_db_ct(c) for c in request.form.getlist("cell_type")]

    genes = [g for g in (_safe_gene(g) for g in raw_genes) if g][:10]
    if not genes:
        genes = ["APOE", "GFAP", "MAPT"]

    try:
        conn = get_connection()
        cur  = conn.cursor()
        # expression_sub side drives via idx_gene (IN list), then joins merged_cells
        clauses = [f"ef.gene IN ({','.join(['%s']*len(genes))})"]
        params  = list(genes)
        if genotype:
            clauses.append(f"mc.APOE_Genotype IN ({','.join(['%s']*len(genotype))})")
            params.extend(genotype)
        if cts:
            clauses.append(f"mc.Final_Cell_Type IN ({','.join(['%s']*len(cts))})")
            params.extend(cts)
        w = "WHERE " + " AND ".join(clauses)
        cur.execute(f"""
            SELECT ef.gene, mc.Final_Cell_Type, mc.APOE_Genotype,
                   AVG(ef.value),
                   SUM(CASE WHEN ef.value > 0 THEN 1 ELSE 0 END) / COUNT(*)
            FROM expression_sub ef
            STRAIGHT_JOIN merged_cells mc ON mc.cell_id = ef.cell_id
            {w}
            GROUP BY ef.gene, mc.Final_Cell_Type, mc.APOE_Genotype
        """, params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify({"type": plot_type, "genes": genes, "data": [
            {"gene": r[0], "cell_type": _norm_ct(r[1]), "genotype": r[2],
             "avg": float(r[3] or 0), "pct": float(r[4] or 0)}
            for r in rows
        ]})
    except Exception as e:
        return jsonify({"error": str(e)})

# ── Cell composition ───────────────────────────────────────────────────────────
@app.route("/cell_composition", methods=["POST"])
def cell_composition():
    plot_type = request.form.get("plot_type", "bar")
    genotype  = request.form.getlist("genotype")
    samples   = request.form.getlist("sample")
    cts       = [_db_ct(c) for c in request.form.getlist("cell_type")]
    try:
        conn = get_connection()
        cur  = conn.cursor()
        clauses, params = [], []
        if genotype:
            clauses.append(f"APOE_Genotype IN ({','.join(['%s']*len(genotype))})")
            params.extend(genotype)
        if samples and "All" not in samples:
            clauses.append(f"dmm_ID IN ({','.join(['%s']*len(samples))})")
            params.extend(samples)
        if cts and "All" not in cts:
            clauses.append(f"Final_Cell_Type IN ({','.join(['%s']*len(cts))})")
            params.extend(cts)
        w = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cur.execute(f"""
            SELECT dmm_ID, APOE_Genotype, Final_Cell_Type,
                   COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY dmm_ID) AS prop
            FROM merged_cells {w}
            GROUP BY dmm_ID, APOE_Genotype, Final_Cell_Type
            ORDER BY Final_Cell_Type
        """, params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        if not rows:
            return jsonify({"error": "No data found.", "data": []})
        return jsonify({"type": plot_type, "data": [
            {"sample": r[0], "genotype": r[1], "group": _norm_ct(r[2]), "prop": float(r[3] or 0)}
            for r in rows
        ]})
    except Exception as e:
        return jsonify({"error": str(e), "data": []})

# ── Cell proportion table ──────────────────────────────────────────────────────
@app.route("/cellprop_table", methods=["POST"])
def cellprop_table():
    genotype  = request.form.getlist("genotype")
    cell_type = _db_ct(request.form.get("cell_type", "all"))
    try:
        conn = get_connection()
        cur  = conn.cursor()
        sql    = "SELECT dmm_ID, APOE_Genotype, Final_Cell_Type, n, prop FROM celltype_proportion WHERE 1=1"
        params = []
        if genotype:
            sql += f" AND APOE_Genotype IN ({','.join(['%s']*len(genotype))})"
            params.extend(genotype)
        if cell_type != "all":
            sql += " AND Final_Cell_Type = %s"
            params.append(cell_type)
        sql += " ORDER BY dmm_ID, Final_Cell_Type"
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify({"data": [
            {"dmm_ID": r[0], "APOE_Genotype": r[1], "Final_Cell_Type": _norm_ct(r[2]),
             "n": int(r[3] or 0), "prop": float(r[4] or 0)}
            for r in rows
        ]})
    except Exception as e:
        return jsonify({"error": str(e), "data": []})

# ── Summary / data table ───────────────────────────────────────────────────────
@app.route("/summary", methods=["POST"])
def summary():
    gene     = _safe_gene(request.form.get("gene", "APOE"))
    genotype = request.form.getlist("genotype")
    ct       = request.form.get("cell_type", "all")
    sample   = request.form.get("sample", "all")
    try:    limit    = max(10, min(int(request.form.get("limit", "100")), 2000))
    except: limit    = 100
    try:    min_expr = float(request.form.get("min_expr", "0"))
    except: min_expr = 0.0
    if not gene:
        return jsonify({"error": "Invalid gene"})
    try:
        conn = get_connection()
        cur  = conn.cursor()
        clauses = ["1=1"]
        params  = [gene]
        if genotype:
            clauses.append(f"mc.APOE_Genotype IN ({','.join(['%s']*len(genotype))})")
            params.extend(genotype)
        if ct != "all":
            clauses.append("mc.Final_Cell_Type = %s"); params.append(ct)
        if sample != "all":
            clauses.append("mc.dmm_ID = %s"); params.append(sample)
        if min_expr > 0:
            clauses.append("COALESCE(ef.value, 0.0) >= %s"); params.append(min_expr)
        w = "WHERE " + " AND ".join(clauses)
        cur.execute(f"""
            SELECT mc.cell_id, COALESCE(ef.value, 0.0), mc.Final_Cell_Type,
                   mc.APOE_Genotype, mc.dmm_ID, mc.UMAP_1, mc.UMAP_2
            FROM merged_cells mc
            LEFT JOIN (SELECT cell_id, value FROM expression_sub WHERE gene = %s) ef
                   ON mc.cell_id = ef.cell_id
            {w} LIMIT {limit}
        """, params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify({"gene": gene, "has_phase": False, "data": [
            {"cell_id": r[0], "expr": float(r[1] or 0), "cell_type": _norm_ct(r[2]),
             "genotype": r[3], "dmm_id": r[4],
             "umap1": float(r[5]) if r[5] is not None else None,
             "umap2": float(r[6]) if r[6] is not None else None}
            for r in rows
        ]})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)