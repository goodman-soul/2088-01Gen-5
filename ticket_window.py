import threading
import time
import random
from ticket_system import TicketSystem


class TicketWindow(threading.Thread):
    def __init__(self, window_id: str, ticket_system: TicketSystem,
                 sale_delay_range: tuple = (0.01, 0.1),
                 refund_probability: float = 0.05,
                 query_probability: float = 0.1):
        super().__init__(name=window_id, daemon=True)
        self.window_id = window_id
        self.ticket_system = ticket_system
        self.sale_delay_min, self.sale_delay_max = sale_delay_range
        self.refund_probability = refund_probability
        self.query_probability = query_probability
        self.tickets_sold = 0
        self.tickets_refunded = 0
        self.queries_performed = 0
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        print(f"[{self.window_id}] 开始售票")

        while not self._stop_event.is_set() and not self.ticket_system.is_sale_stopped():
            action = random.random()

            if action < self.query_probability:
                self._perform_query()
            elif action < self.query_probability + self.refund_probability:
                self._try_refund()
            else:
                self._try_sell()

            time.sleep(random.uniform(self.sale_delay_min, self.sale_delay_max))

        print(f"[{self.window_id}] 停止售票。累计售票 {self.tickets_sold} 张，退票 {self.tickets_refunded} 张，查询 {self.queries_performed} 次")

    def _perform_query(self) -> None:
        available = self.ticket_system.get_available_count()
        self.queries_performed += 1
        if random.random() < 0.1:
            print(f"[{self.window_id}] 查询余票：剩余 {available} 张")

    def _try_sell(self) -> None:
        available_seats = self.ticket_system.get_available_seats()
        if not available_seats:
            if random.random() < 0.05:
                print(f"[{self.window_id}] 无票可售")
            return

        seat_id = random.choice(available_seats)
        success = self.ticket_system.sell_ticket(seat_id, self.window_id)

        if success:
            self.tickets_sold += 1
            if random.random() < 0.15:
                print(f"[{self.window_id}] 售出 {seat_id} 号座位")
        else:
            if random.random() < 0.05:
                print(f"[{self.window_id}] 售票失败：{seat_id} 号座位已被其他窗口售出")

    def _try_refund(self) -> None:
        my_sold_seats = self.ticket_system.get_sold_seats_by_window(self.window_id)
        if not my_sold_seats:
            return

        if random.random() < 0.3:
            seat_id = random.choice(my_sold_seats)
            success = self.ticket_system.refund_ticket(seat_id, self.window_id)
            if success:
                self.tickets_refunded += 1
                print(f"[{self.window_id}] 办理退票：{seat_id} 号座位")
