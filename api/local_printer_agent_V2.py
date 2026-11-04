import os
import datetime
import time
import requests
from PIL import Image, ImageDraw, ImageFont
from escpos.printer import Network
from sqlalchemy import func
from zoneinfo import ZoneInfo

VERCEL_API_URL = "https://bakery-backend-wimuti.vercel.app/api"
PRINTER_IP = "192.168.1.87"  # IP เครื่องพิมพ์ Worrex Wi-Fi

try:
    font_title = ImageFont.truetype("Fonts/tahomabd.ttf", 26)
    font_bold = ImageFont.truetype("Fonts/tahomabd.ttf", 22)
    font_normal = ImageFont.truetype("Fonts/tahoma.ttf", 22)
    font_small = ImageFont.truetype("Fonts/tahoma.ttf", 20)
except:
    font_title = font_bold = font_normal = font_small = ImageFont.load_default()

#----------------------------------------------------------------------------------------------------------
# 1. ฟังก์ชัน "ใบออเดอร์" สำหรับส่งเข้าครัว (ไม่มี Logo, ไม่มี QR Code, หัวข้อ ORDER)
def create_order_ticket_image(order):
    img_width = 576
    margin = 20
    lines = []
    
    lines.append(("center", "\n", font_normal))
    lines.append(("center", "** ORDER TICKET **", font_title))
    lines.append(("center", "-" * 66, font_normal))
    
    order_id = order.get('id', '-')
    created_at = order.get('created_at', '')
    customer_name = order.get('customer_name') or 'หน้าร้าน'
    dt_th = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00')).astimezone(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y %H:%M:%S")

    lines.append(("left_right", (f"Order : ", f"#{order_id}"), font_bold))
    lines.append(("left_right", (f"เวลา : ", f"{dt_th}"), font_normal))
    lines.append(("left", f"ลูกค้า: {customer_name}", font_bold))
    lines.append(("center", "-" * 66, font_normal))

    lines.append(("left_right", ("Qty x Description", "Item"), font_normal))
    lines.append(("center", "-" * 66, font_normal))

    items = order.get('items') or order.get('order_items') or []
    qty_total = 0
    for item in items:
        product_info = item.get('product') or {}
        p_name = product_info.get('name') or item.get('product_name') or 'สินค้า'
        qty = item.get('quantity', 1)
        qty_total += qty

        item_text = f"{qty}x {p_name}"
        lines.append(("left", item_text, font_normal))

        if item.get('custom_text'):
            lines.append(("left", f"  - หน้าเค้ก: \"{item['custom_text']}\"", font_small))

    lines.append(("center", "-" * 66, font_normal))
    lines.append(("left_right", ("Total Quantity:", f"{qty_total} PCS."), font_bold))

    notes = order.get('notes')
    if notes:
        lines.append(("center", "-" * 66, font_normal))
        lines.append(("left", f"📌 Notes: {notes}", font_bold))

    lines.append(("center", "\n\n", font_normal))

    line_height = 26
    img_height = len(lines) * line_height + 40
    img = Image.new('RGB', (img_width, img_height), color='white')
    d = ImageDraw.Draw(img)

    current_y = margin
    for line_type, text_data, font in lines:
        if line_type == "center":
            bbox = d.textbbox((0, 0), text_data, font=font)
            text_width = bbox[2] - bbox[0]
            x = (img_width - text_width) / 2
            d.text((x, current_y), text_data, fill='black', font=font)
        elif line_type == "left":
            d.text((margin, current_y), text_data, fill='black', font=font)
        elif line_type == "left_right":
            left_text, right_text = text_data
            d.text((margin, current_y), left_text, fill='black', font=font)
            bbox = d.textbbox((0, 0), right_text, font=font)
            r_width = bbox[2] - bbox[0]
            d.text((img_width - margin - r_width, current_y), right_text, fill='black', font=font)
        
        current_y += line_height

    return img.crop((0, 0, img_width, current_y + 10))

#----------------------------------------------------------------------------------------------------------
# 2. ฟังก์ชัน "ใบเสร็จรับเงิน" ต้นฉบับ (มี Logo และ QR Code)
def create_receipt_image(order):
    img_width = 576  
    margin = 20
    lines = []
    
    logo_img = None
    qrcode_img = None
    logo_path = "images/logo.jpg" 
    qrcode_path = "images/qrcode.jpg"

    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("L") 
            basewidth = 300
            wpercent = (basewidth / float(logo.size[0]))
            hsize = int(float(logo.size[1]) * float(wpercent))
            logo = logo.resize((basewidth, hsize), Image.Resampling.LANCZOS)
            logo_img = logo
        except Exception as e:
            print(f"[Error] โหลดโลโก้ไม่สำเร็จ: {e}")

    if os.path.exists(qrcode_path):
        try:
            qrc = Image.open(qrcode_path).convert("L")
            qr_size = 320 
            qrc = qrc.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
            qrcode_img = qrc
        except Exception as e:
            print(f"[Error] โหลด QR Code ไม่สำเร็จ: {e}")

    lines.append(("center", "\n", font_normal))
    lines.append(("center", "RECEIPT/ORDER", font_normal))
    lines.append(("center", "-" * 66, font_normal))
    
    order_id = order.get('id', '-')
    created_at = order.get('created_at', '')
    customer_name = order.get('customer_name') or 'หน้าร้าน'
    payment_method = order.get('payment_method') or '-'
    dt_th = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00')).astimezone(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y %H:%M:%S")

    lines.append(("left_right", (f"Order : ", f"#{order_id}"), font_normal))
    lines.append(("left_right", (f"เวลา : ", f"{dt_th}"), font_normal))
    lines.append(("left_right", (f"ลูกค้า: {customer_name}", f"ชำระ: {payment_method}"), font_normal))
    lines.append(("center", "-" * 66, font_normal))

    lines.append(("left_right", ("Qty x Description", "Total"), font_normal))
    lines.append(("center", "-" * 66, font_normal))

    items = order.get('items') or order.get('order_items') or []
    qty_total = 0
    for item in items:
        product_info = item.get('product') or {}
        p_name = product_info.get('name') or item.get('product_name') or 'สินค้า'
        qty = item.get('quantity', 1)
        qty_total += qty
        price = item.get('price', 0)
        total_item_price = price * qty

        item_text = f"{qty}x {p_name} ({price:.2f}/ea)"
        price_text = f"{total_item_price:.2f}"
        lines.append(("item_row", (item_text, price_text), font_small))

        if item.get('custom_text'):
            lines.append(("left", f"  - หน้าเค้ก: \"{item['custom_text']}\"", font_small))

    lines.append(("center", "-" * 66, font_normal))
    lines.append(("left", f"Total: {qty_total} PCS.", font_normal))

    subtotal = order.get('subtotal_price') or order.get('total_price') or 0
    lines.append(("left_right", ("Sub Total:", f"{subtotal:.2f} ฿"), font_normal))

    discount = order.get('discount_price', 0) or 0
    if discount > 0:
        lines.append(("left_right", ("Discount:", f"-{discount:.2f} ฿"), font_normal))

    grand_total = order.get('grandtotal_price') or order.get('total_price') or 0
    lines.append(("center", "-" * 66, font_normal))
    lines.append(("left_right", ("Net Total:", f"{grand_total:.2f} ฿"), font_bold))

    notes = order.get('notes')
    if notes:
        lines.append(("center", "-" * 66, font_normal))
        lines.append(("left", f"📌 Notes: {notes}", font_normal))

    lines.append(("center", "\n\n", font_normal))
    lines.append(("center", "-" * 48, font_normal))
    lines.append(("center", "*** Thank you ***", font_small))
    lines.append(("center", "\n", font_normal))

    logo_height = (logo_img.size[1] + 10) if logo_img else 0
    qrcode_height = (qrcode_img.size[1] + 15) if qrcode_img else 0

    line_height = 24
    img_height = len(lines) * line_height + 60 + logo_height + qrcode_height
    img = Image.new('RGB', (img_width, img_height), color='white')
    d = ImageDraw.Draw(img)

    current_y = margin
    
    if logo_img:
        logo_x = (img_width - logo_img.size[0]) / 2
        img.paste(logo_img, (int(logo_x), int(current_y)))
        current_y += logo_img.size[1] + 15

    for line_type, text_data, font in lines:
        if line_type == "center":
            bbox = d.textbbox((0, 0), text_data, font=font)
            text_width = bbox[2] - bbox[0]
            x = (img_width - text_width) / 2
            d.text((x, current_y), text_data, fill='black', font=font)
        elif line_type == "left":
            d.text((margin, current_y), text_data, fill='black', font=font)
        elif line_type == "left_right":
            left_text, right_text = text_data
            d.text((margin, current_y), left_text, fill='black', font=font)
            bbox = d.textbbox((0, 0), right_text, font=font)
            r_width = bbox[2] - bbox[0]
            d.text((img_width - margin - r_width, current_y), right_text, fill='black', font=font)
        elif line_type == "item_row":
            item_text, price_text = text_data
            d.text((margin, current_y), item_text, fill='black', font=font)
            bbox = d.textbbox((0, 0), price_text, font=font)
            p_width = bbox[2] - bbox[0]
            d.text((img_width - margin - p_width, current_y), price_text, fill='black', font=font)
        
        current_y += line_height

    if qrcode_img:
        current_y += 5
        qrcode_x = (img_width - qrcode_img.size[0]) / 2
        img.paste(qrcode_img, (int(qrcode_x), int(current_y)))
        current_y += qrcode_img.size[1] + 10

    return img.crop((0, 0, img_width, current_y + 10))

#----------------------------------------------------------------------------------------------------------
# 3. ฟังก์ชัน "ใบเสร็จรับเงิน" Copy (มี Logo และ QR Code)
def create_receipt_copy_image(order):
    img_width = 576  
    margin = 20
    lines = []
    
    logo_img = None
    qrcode_img = None
    logo_path = "images/logo.jpg" 
    qrcode_path = "images/qrcode.jpg"

    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("L") 
            basewidth = 300
            wpercent = (basewidth / float(logo.size[0]))
            hsize = int(float(logo.size[1]) * float(wpercent))
            logo = logo.resize((basewidth, hsize), Image.Resampling.LANCZOS)
            logo_img = logo
        except Exception as e:
            print(f"[Error] โหลดโลโก้ไม่สำเร็จ: {e}")

    if os.path.exists(qrcode_path):
        try:
            qrc = Image.open(qrcode_path).convert("L")
            qr_size = 320 
            qrc = qrc.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
            qrcode_img = qrc
        except Exception as e:
            print(f"[Error] โหลด QR Code ไม่สำเร็จ: {e}")

    lines.append(("center", "\n", font_normal))
    lines.append(("center", "RECEIPT/ORDER (COPY)", font_title))
    lines.append(("center", "-" * 66, font_normal))
    
    order_id = order.get('id', '-')
    created_at = order.get('created_at', '')
    customer_name = order.get('customer_name') or 'หน้าร้าน'
    payment_method = order.get('payment_method') or '-'
    dt_th = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00')).astimezone(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y %H:%M:%S")

    lines.append(("left_right", (f"Order : ", f"#{order_id}"), font_normal))
    lines.append(("left_right", (f"เวลา : ", f"{dt_th}"), font_normal))
    lines.append(("left_right", (f"ลูกค้า: {customer_name}", f"ชำระ: {payment_method}"), font_normal))
    lines.append(("center", "-" * 66, font_normal))

    lines.append(("left_right", ("Qty x Description", "Total"), font_normal))
    lines.append(("center", "-" * 66, font_normal))

    items = order.get('items') or order.get('order_items') or []
    qty_total = 0
    for item in items:
        product_info = item.get('product') or {}
        p_name = product_info.get('name') or item.get('product_name') or 'สินค้า'
        qty = item.get('quantity', 1)
        qty_total += qty
        price = item.get('price', 0)
        total_item_price = price * qty

        item_text = f"{qty}x {p_name} ({price:.2f}/ea)"
        price_text = f"{total_item_price:.2f}"
        lines.append(("item_row", (item_text, price_text), font_small))

        if item.get('custom_text'):
            lines.append(("left", f"  - หน้าเค้ก: \"{item['custom_text']}\"", font_small))

    lines.append(("center", "-" * 66, font_normal))
    lines.append(("left", f"Total: {qty_total} PCS.", font_normal))

    subtotal = order.get('subtotal_price') or order.get('total_price') or 0
    lines.append(("left_right", ("Sub Total:", f"{subtotal:.2f} ฿"), font_normal))

    discount = order.get('discount_price', 0) or 0
    if discount > 0:
        lines.append(("left_right", ("Discount:", f"-{discount:.2f} ฿"), font_normal))

    grand_total = order.get('grandtotal_price') or order.get('total_price') or 0
    lines.append(("center", "-" * 66, font_normal))
    lines.append(("left_right", ("Net Total:", f"{grand_total:.2f} ฿"), font_bold))

    notes = order.get('notes')
    if notes:
        lines.append(("center", "-" * 66, font_normal))
        lines.append(("left", f"📌 Notes: {notes}", font_normal))

    lines.append(("center", "\n\n", font_normal))
    lines.append(("center", "-" * 48, font_normal))
    lines.append(("center", "*** Thank you ***", font_small))
    lines.append(("center", "\n", font_normal))

    logo_height = (logo_img.size[1] + 10) if logo_img else 0
    qrcode_height = (qrcode_img.size[1] + 15) if qrcode_img else 0

    line_height = 24
    img_height = len(lines) * line_height + 60 + logo_height + qrcode_height
    img = Image.new('RGB', (img_width, img_height), color='white')
    d = ImageDraw.Draw(img)

    current_y = margin
    
    if logo_img:
        logo_x = (img_width - logo_img.size[0]) / 2
        img.paste(logo_img, (int(logo_x), int(current_y)))
        current_y += logo_img.size[1] + 15

    for line_type, text_data, font in lines:
        if line_type == "center":
            bbox = d.textbbox((0, 0), text_data, font=font)
            text_width = bbox[2] - bbox[0]
            x = (img_width - text_width) / 2
            d.text((x, current_y), text_data, fill='black', font=font)
        elif line_type == "left":
            d.text((margin, current_y), text_data, fill='black', font=font)
        elif line_type == "left_right":
            left_text, right_text = text_data
            d.text((margin, current_y), left_text, fill='black', font=font)
            bbox = d.textbbox((0, 0), right_text, font=font)
            r_width = bbox[2] - bbox[0]
            d.text((img_width - margin - r_width, current_y), right_text, fill='black', font=font)
        elif line_type == "item_row":
            item_text, price_text = text_data
            d.text((margin, current_y), item_text, fill='black', font=font)
            bbox = d.textbbox((0, 0), price_text, font=font)
            p_width = bbox[2] - bbox[0]
            d.text((img_width - margin - p_width, current_y), price_text, fill='black', font=font)
        
        current_y += line_height

    if qrcode_img:
        current_y += 5
        qrcode_x = (img_width - qrcode_img.size[0]) / 2
        img.paste(qrcode_img, (int(qrcode_x), int(current_y)))
        current_y += qrcode_img.size[1] + 10

    return img.crop((0, 0, img_width, current_y + 10))

#----------------------------------------------------------------------------------------------------------
# 4. กระบวนการพิมพ์แยกตามประเภทที่ถูกเลือก ใบออเดอร์/ใบเสร็จรับเงิน (is_print_order หรือ is_print_receipt)
def print_receipt_to_worrex(order):
    try:
        printer = Network(PRINTER_IP, port=9100, timeout=5, profile="default")
        
        is_print_order = order.get('is_print_order', False)
        is_print_receipt = order.get('is_print_receipt', False)
        
        printed_any = False

        # เลือกพิมพ์เฉพาะใบออเดอร์
        if is_print_order:
            order_image = create_order_ticket_image(order)
            printer.image(order_image)
            printer.cut()
            printed_any = True
            print(f"[Success] พิมพ์ 'ใบออเดอร์' สำหรับออเดอร์ #{order['id']} สำเร็จ")

        # เลือกพิมพ์เฉพาะใบเสร็จรับเงิน (พิมพ์ตัวจริง + สำเนา)
        if is_print_receipt:
            receipt_image = create_receipt_image(order)
            printer.image(receipt_image)
            printer.cut()

            receipt_copy_image = create_receipt_copy_image(order)
            printer.image(receipt_copy_image)
            printer.cut()
            printed_any = True
            print(f"[Success] พิมพ์ 'ใบเสร็จรับเงิน + สำเนา' สำหรับออเดอร์ #{order['id']} สำเร็จ")

        if not printed_any:
            print(print(f"[-] ออเดอร์ #{order['id']} ไม่ได้ระบุประเภทงานพิมพ์"))
            return False

        return True
    except Exception as e:
        print(f"[Error] พิมพ์ออเดอร์ #{order['id']} ไม่สำเร็จ: {str(e)}")
        return False

#----------------------------------------------------------------------------------------------------------
# สั่งให้ python ทำงานเพื่อตรวจสอบ Que Printer
def start_agent():
    print(f"[*] Local Printer Agent ทำงานแล้ว (พิมพ์ออเดอร์/ใบเสร็จ) | IP: {PRINTER_IP}")
    while True:
        try:
            response = requests.get(f"{VERCEL_API_URL}/orders/requested-print")
            if response.status_code == 200:
                orders = response.json()
                for order in orders:
                    success = print_receipt_to_worrex(order)
                    if success:
                        requests.patch(f"{VERCEL_API_URL}/orders/{order['id']}/mark-printed")
        except Exception as e:
            print(f"[-] เชื่อมต่อ Cloud Printer ไม่สำเร็จ: {str(e)}")
        
        time.sleep(3)

if __name__ == "__main__":
    start_agent()