import time
import requests
from escpos.printer import Network

VERCEL_API_URL = "https://bakery-backend-wimuti.vercel.app/api"
PRINTER_IP = "192.168.1.87"  # IP เครื่องพิมพ์ Worrex Wi-Fi

def print_receipt_to_worrex(order):
    try:
        printer = Network(PRINTER_IP, port=9100, timeout=5)
        
        # จัดรูปแบบใบเสร็จ 80mm
        printer.set(align='center', bold=True, width=2, height=2)
        printer.text("WIMUTI BAKE & DRIP\n")
        printer.set(align='center', bold=False, width=1, height=1)
        printer.text("--------------------------------\n")
        printer.text(f"Order ID: #{order['id']}\n")
        printer.text(f"Customer: {order.get('customer_name', 'หน้าร้าน')}\n")
        printer.text(f"Time: {order.get('created_at', '')}\n")
        printer.text("--------------------------------\n")

        printer.set(align='left', bold=True)
        for item in order.get('items', []):
            p_name = item.get('product', {}).get('name', 'สินค้า')
            qty = item.get('quantity', 1)
            price = item.get('price', 0)
            printer.text(f"{p_name[:18]:<18} x{qty:<3} {(price*qty):>6.2f}\n")
            if item.get('custom_text'):
                printer.text(f"  - หน้าเค้ก: {item['custom_text']}\n")

        printer.text("--------------------------------\n")
        printer.set(align='right', bold=True)
        printer.text(f"TOTAL: {order.get('grandtotal_price', 0):.2f} THB\n")
        
        if order.get('notes'):
            printer.text("--------------------------------\n")
            printer.set(align='left', bold=False)
            printer.text(f"NOTE: {order['notes']}\n")

        printer.text("--------------------------------\n")
        printer.set(align='center', bold=False)
        printer.text("Thank you for your order!\n\n\n")
        printer.cut()
        
        print(f"[Success] พิมพ์ออเดอร์ #{order['id']} ออกเครื่อง Worrex สำเร็จ")
        return True
    except Exception as e:
        print(f"[Error] พิมพ์ออเดอร์ #{order['id']} ไม่สำเร็จ: {str(e)}")
        return False

def start_agent():
    print(f"[*] Local Agent กำลังรอคำสั่งพิมพ์เฉพาะออร์เดอร์ที่กดปุ่ม... (IP: {PRINTER_IP})")
    while True:
        try:
            # ดึงเฉพาะออร์เดอร์ที่มีการกดสั่งพิมพ์เข้ามาเท่านั้น
            response = requests.get(f"{VERCEL_API_URL}/orders/requested-print")
            if response.status_code == 200:
                orders = response.json()
                for order in orders:
                    success = print_receipt_to_worrex(order)
                    if success:
                        # แจ้ง Vercel ว่าพิมพ์เสร็จแล้ว ให้ปิดคำขอพิมพ์นี้ทันที
                        requests.patch(f"{VERCEL_API_URL}/orders/{order['id']}/mark-printed")
                        
        except Exception as e:
            print(f"[-] เชื่อมต่อ Cloud ไม่สำเร็จ: {str(e)}")
        
        time.sleep(3) # เช็คคำสั่งพิมพ์ใหม่ทุกๆ 3 วินาที

if __name__ == "__main__":
    start_agent()