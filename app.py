from flask import Flask, render_template, request, jsonify
import pyodbc

app = Flask(__name__)

# ✅ Define connection string here (before functions use it)
CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=garimadb.reckonerp.online,5051;"
    "DATABASE=GM_StockView;"
    "UID=sa;"
    "PWD=RI@123I@#FJE;"
    "TrustServerCertificate=yes;"
)

def get_db_connection():
    return pyodbc.connect(CONNECTION_STRING)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_supplier', methods=['POST'])
def get_supplier():
    gst_number = request.form['gst_number']
    sql = """
        SELECT ac_acno AS SupplierCode, AC_name AS SupplierName,
               Ac_address1 AS SupplierAddress1, Ac_address2 AS SupplierAddress2
        FROM Garho25..accounts
        WHERE Ac_gst_number = ?
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql, gst_number)
    row = cursor.fetchone()
    conn.close()

    if row:
        supplier = {
            'SupplierCode': row.SupplierCode,
            'SupplierName': row.SupplierName,
            'SupplierAddress1': row.SupplierAddress1,
            'SupplierAddress2': row.SupplierAddress2
        }
    else:
        supplier = None

    return jsonify({'data': supplier})

@app.route('/check_grn', methods=['POST'])
def check_grn():
    store_code = request.form['store_code'].strip()
    grn_number = request.form['grn_number'].strip()
    purno = store_code + grn_number

    sql = """
        SELECT COUNT(*) FROM PurchaseGRN 
        WHERE LTRIM(RTRIM(PURNO)) = LTRIM(RTRIM(?))
    """

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql, purno)
    count = cursor.fetchone()[0]
    conn.close()

    return jsonify({'exists': count > 0})

@app.route('/get_item', methods=['POST'])
def get_item():
    code = request.form['code'].strip()
    store_code = request.form['store_code'].strip()
    is_ean = request.form['is_ean'] == 'true'

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1️⃣ Try from GMStockbal first
    sql1 = """
        SELECT TOP 1
            SB_ITEM AS ItemCode,
            ItemName,
            SB_P_RATE AS PurRate,
            SB_Rate_A AS SalePrice,
            SB_M_RATE AS MRP,
            SB_BATCHNO AS LotNo,
            SB_BAR_CODE AS EANCode
        FROM GM_StockView..GMStockbal
        WHERE {} = ?
          AND SB_FIRM = ?
        ORDER BY SB_P_BillDate DESC
    """.format("SB_BAR_CODE" if is_ean else "SB_ITEM")

    cursor.execute(sql1, code, store_code)
    row = cursor.fetchone()

    if row:
        item = {
            'ItemCode': row.ItemCode,
            'ItemName': row.ItemName,
            'PurRate': float(row.PurRate or 0),
            'SalePrice': float(row.SalePrice or 0),
            'MRP': float(row.MRP or 0),
            'LotNo': row.LotNo,
            'EANCode': row.EANCode  # ✅ FROM STOCKBAL
        }
    else:
        # 2️⃣ Fallback to GM_ItemList
        sql2 = """
            SELECT TOP 1
                ItemCode,
                ItemName,
                EANCode
            FROM GM_ItemList
            WHERE {} = ?
        """.format("EANCode" if is_ean else "ItemCode")

        cursor.execute(sql2, code)
        row2 = cursor.fetchone()

        if row2:
            item = {
                'ItemCode': row2.ItemCode,
                'ItemName': row2.ItemName,
                'PurRate': 0,
                'SalePrice': 0,
                'MRP': 0,
                'LotNo': '',
                'EANCode': row2.EANCode  # ✅ FROM ITEMLIST
            }
        else:
            item = None

    conn.close()
    return jsonify({'data': item})



@app.route('/submit_grn', methods=['POST'])
def submit_grn():
    data = request.get_json()

    store_code = data['StoreCode']
    grn_number = data['GRNNumber']
    grn_date = data['GRNDate']
    order_number = data['OrderNumber']
    order_date = data['OrderDate']
    gst_number = data['GSTNumber']
    supplier_code = data['SupplierCode']
    supplier_name = data['SupplierName']
    address1 = data['SupplierAddress1']
    address2 = data['SupplierAddress2']
    items = data['Items']

    conn = get_db_connection()
    cursor = conn.cursor()

    for item in items:
        sql = """
            INSERT INTO PurchaseGRN 
            (PURNO, Storecode, GRNNumber, GRNDate, OrderNumber, OrderDate,
             ItemCode, ItemName, EANCode, LotNumber, Qty, FQty, Rate, Disc, MRP, SaleRate,
             GSTNumber, SupplierCode, SupplierName, Address1, Address2)
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """
        cursor.execute(
            sql,
            store_code + grn_number,
            store_code,
            grn_number,
            grn_date,
            order_number,
            order_date,
            item['ItemCode'],
            item['ItemName'],
            item['EANCode'],
            item['LotNumber'],
            float(item['Qty'] or 0),
            float(item['FQty'] or 0),
            float(item['Rate'] or 0),
            float(item['Disc'] or 0),
            float(item['MRP'] or 0),
            float(item['SaleRate'] or 0),
            gst_number,
            supplier_code,
            supplier_name,
            address1,
            address2
        )

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'GRN saved successfully!'})



# --- START OF CHANGES ---
# This is the only part that has been modified.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # don't set ssl_context


# --- END OF CHANGES ---


