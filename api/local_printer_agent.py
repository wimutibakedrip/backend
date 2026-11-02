import time
import requests
from escpos.printer import Network

# ตั้งค่า URL ของ Backend บน Vercel และ IP ของเครื่องพิมพ์ Worrex ในร้าน
VERCEL_API_URL = "https://bakery-backend-wimuti.vercel.app/api"
PRINTER_IP = "192.168.1.87"  # IP ของเครื่องพิมพ์ Worrex Wi-Fi

def print_receipt_to_worrex(order):
    try:
        # เชื่อมต่อเครื่องพิมพ์ผ่าน Network IP (พอร์ตมาตรฐาน ESC/POS คือ 9100)
        printer = Network(PRINTER_IP, port=9100, timeout=5)
        
        # จัดรูปแบบหัวบิล 80mm
        printer.set(align='center', bold=True, width=2, height=2)
        printer.text("WIMUTI BAKE & DRIP\n")
        printer.set(align='center', bold=False, width=1, height=1)
        printer.text("--------------------------------\n")
        printer.text(f"Order ID: #{order['id']}\n")
        printer.text(f"Customer: {order.get('customer_name', 'หน้าร้าน')}\n")
        printer.text(f"Time: {order.get('created_at', '')}\n")
        printer.text("--------------------------------\n")

        # รายการสินค้า
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
        
        print(f"[Success] สั่งพิมพ์ออเดอร์ #{order['id']} ออกเครื่อง Worrex สำเร็จ")
        return True
    except Exception as e:
        print(f"[Error] ไม่สามารถพิมพ์ออเดอร์ #{order['id']}: {str(e)}")
        return False

def start_agent():
    print(f"[*] Local Print Agent ทำงานแล้ว | เชื่อมต่อเครื่องพิมพ์ Worrex IP: {PRINTER_IP}")
    while True:
        try:
            # ดึงรายการที่ยังไม่ได้พิมพ์จาก Vercel
            response = requests.get(f"{VERCEL_API_URL}/orders/pending-print")
            if response.status_code == 200:
                orders = response.json()
                for order in orders:
                    # สั่งพิมพ์ออกเครื่อง Worrex
                    success = print_receipt_to_worrex(order)
                    if success:
                        # แจ้ง Vercel ว่าออเดอร์นี้พิมพ์แล้ว เพื่อไม่ให้พิมพ์ซ้ำ
                        requests.patch(
                            f"{VERCEL_API_URL}/orders/{order['id']}/print-status",
                            json={"is_printed": True}
                        )
        except Exception as e:
            print(f"[-] ขัดข้องในการเชื่อมต่อ Cloud Vercel: {str(e)}")
        
        time.sleep(5)  # วนลูปเช็คคิวใหม่ทุกๆ 5 วินาที

if __name__ == "__main__":
    start_agent()