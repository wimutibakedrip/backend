import datetime
import time
import requests
from PIL import Image, ImageDraw, ImageFont
from escpos.printer import Network
from sqlalchemy import func
from zoneinfo import ZoneInfo

VERCEL_API_URL = "https://bakery-backend-wimuti.vercel.app/api"
PRINTER_IP = "192.168.1.87"  # IP เครื่องพิมพ์ Worrex Wi-Fi

def create_receipt_image(order):
    img_width = 576  # ความกว้างกระดาษ 80 มม.
    margin = 20

    try:
        font_title = ImageFont.truetype("C:/Windows/Fonts/tahomabd.ttf", 24)
        font_bold = ImageFont.truetype("C:/Windows/Fonts/tahomabd.ttf", 22)
        font_normal = ImageFont.truetype("C:/Windows/Fonts/tahoma.ttf", 22)
        font_small = ImageFont.truetype("C:/Windows/Fonts/tahoma.ttf", 18)
    except:
        font_title = font_bold = font_normal = font_small = ImageFont.load_default()

    lines = []
    # ส่วนหัวใบเสร็จ
    lines.append(("center", "WIMUTI BAKE & DRIP", font_title))
    lines.append(("center", "Order Ticket", font_small))
    lines.append(("center", "-" * 58, font_normal))
    
    # ข้อมูลออเดอร์
    order_id = order.get('id', '-')
    created_at = str(order.get('created_at', ''))[:19]
    customer_name = order.get('customer_name') or 'หน้าร้าน'
    payment_method = order.get('payment_method') or '-'

    dt = datetime.datetime.fromisoformat(created_at)
    dt_th = dt.replace(tzinfo=ZoneInfo("Asia/Bangkok"))

    lines.append(("left_right", (f"Order : ", f"#{order_id}"), font_normal))
    lines.append(("left_right", (f"เวลา : ", f"{dt_th}"), font_normal))
    lines.append(("left_right", (f"ลูกค้า: {customer_name}", f"ชำระ: {payment_method}"), font_normal))
    lines.append(("center", "-" * 48, font_normal))

    # หัวตารางรายการสินค้า
    lines.append(("left_right", ("รายการ x จำนวน", "ราคา"), font_bold))
    lines.append(("center", "-" * 48, font_normal))

    # รายการสินค้า (รองรับทั้ง key items หรือ order_items)
    items = order.get('items') or order.get('order_items') or []
    for item in items:
        product_info = item.get('product') or {}
        p_name = product_info.get('name') or item.get('product_name') or 'สินค้า'
        qty = item.get('quantity', 1)
        price = item.get('price', 0)
        total_item_price = price * qty

        item_text = f"{qty}x {p_name}"
        price_text = f"{total_item_price:.2f}"
        lines.append(("item_row", (item_text, price_text), font_normal))

        # ข้อความเพิ่มเติมหน้าเค้ก
        if item.get('custom_text'):
            lines.append(("left", f"  - หน้าเค้ก: \"{item['custom_text']}\"", font_small))

    # ส่วนสรุปราคา
    lines.append(("center", "-" * 48, font_normal))
    
    # แก้ไขจุดที่เคยใช้ ?? ให้เป็นวิธีมาตรฐานของ Python
    subtotal = order.get('subtotal_price')
    if subtotal is None:
        subtotal = order.get('total_price') or 0

    lines.append(("left_right", ("รวมเงิน:", f"{subtotal:.2f} ฿"), font_normal))

    discount = order.get('discount_price', 0) or 0
    if discount > 0:
        lines.append(("left_right", ("ส่วนลด:", f"-{discount:.2f} ฿"), font_normal))

    grand_total = order.get('grandtotal_price')
    if grand_total is None:
        grand_total = order.get('total_price') or 0

    lines.append(("left_right", ("ยอดสุทธิ:", f"{grand_total:.2f} ฿"), font_bold))

    # หมายเหตุออเดอร์
    notes = order.get('notes')
    if notes:
        lines.append(("center", "-" * 48, font_normal))
        lines.append(("left", f"📌 หมายเหตุ: {notes}", font_normal))

    lines.append(("center", "-" * 48, font_normal))
    lines.append(("center", "*** ขอบคุณค่ะ ***", font_small))
    lines.append(("center", "\n\n", font_normal))

    # วาดลงภาพ
    line_height = 24
    img_height = len(lines) * line_height + 60
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
        elif line_type == "item_row":
            item_text, price_text = text_data
            d.text((margin, current_y), item_text, fill='black', font=font)
            bbox = d.textbbox((0, 0), price_text, font=font)
            p_width = bbox[2] - bbox[0]
            d.text((img_width - margin - p_width, current_y), price_text, fill='black', font=font)
        
        current_y += line_height

    return img.crop((0, 0, img_width, current_y + 10))

def print_receipt_to_worrex(order):
    try:
        printer = Network(PRINTER_IP, port=9100, timeout=5)
        
        # แปลงข้อมูลออเดอร์เป็นรูปภาพที่รองรับภาษาไทย
        receipt_image = create_receipt_image(order)
        
        # สั่งพิมพ์ภาพออกเครื่องพิมพ์ความร้อน
        printer.image(receipt_image)
        printer.cut()
        
        print(f"[Success] พิมพ์ออเดอร์ #{order['id']} (รองรับภาษาไทย) สำเร็จ")
        return True
    except Exception as e:
        print(f"[Error] พิมพ์ออเดอร์ #{order['id']} ไม่สำเร็จ: {str(e)}")
        return False

def start_agent():
    print(f"[*] Local Agent ทำงานแล้ว (โหมดพิมพ์ภาษาไทยผ่านภาพ) | IP: {PRINTER_IP}")
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
            print(f"[-] เชื่อมต่อ Cloud ไม่สำเร็จ: {str(e)}")
        
        time.sleep(3)

if __name__ == "__main__":
    start_agent()