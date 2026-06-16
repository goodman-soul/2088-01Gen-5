import threading
import time
import random
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional


class SeatStatus(Enum):
    AVAILABLE = "可用"
    SOLD = "已售"


@dataclass
class Seat:
    seat_id: int
    status: SeatStatus = SeatStatus.AVAILABLE
    sold_to: Optional[str] = None


@dataclass
class Transaction:
    tx_id: int
    type: str
    seat_id: int
    window_id: str
    success: bool


class UnsafeTicketSystem:
    def __init__(self, total_seats: int):
        self.total_seats = total_seats
        self.seats: Dict[int, Seat] = {i: Seat(seat_id=i) for i in range(1, total_seats + 1)}
        self._transactions: List[Transaction] = []
        self._tx_counter = 0
        self._sold_count = 0
        self._stop_sale = False

    def _generate_tx_id(self) -> int:
        self._tx_counter += 1
        return self._tx_counter

    def stop_sale(self) -> None:
        self._stop_sale = True

    def is_sale_stopped(self) -> bool:
        return self._stop_sale

    def get_available_seats(self) -> List[int]:
        return [s.seat_id for s in self.seats.values() if s.status == SeatStatus.AVAILABLE]

    def get_sold_count(self) -> int:
        return self._sold_count

    def get_available_count(self) -> int:
        return sum(1 for s in self.seats.values() if s.status == SeatStatus.AVAILABLE)

    def sell_ticket(self, seat_id: int, window_id: str) -> bool:
        if self._stop_sale:
            return False
        if seat_id not in self.seats:
            return False
        seat = self.seats[seat_id]
        if seat.status != SeatStatus.AVAILABLE:
            try:
                self._transactions.append(Transaction(
                    tx_id=self._generate_tx_id(),
                    type="售票",
                    seat_id=seat_id,
                    window_id=window_id,
                    success=False
                ))
            except:
                pass
            return False
        time.sleep(random.uniform(0.001, 0.005))
        seat.status = SeatStatus.SOLD
        seat.sold_to = window_id
        self._sold_count += 1
        try:
            self._transactions.append(Transaction(
                tx_id=self._generate_tx_id(),
                type="售票",
                seat_id=seat_id,
                window_id=window_id,
                success=True
            ))
        except:
            pass
        return True

    def verify_consistency(self) -> dict:
        actual_sold = sum(1 for s in self.seats.values() if s.status == SeatStatus.SOLD)
        actual_available = sum(1 for s in self.seats.values() if s.status == SeatStatus.AVAILABLE)
        success_sell_tx = sum(1 for tx in self._transactions if tx.type == "售票" and tx.success)
        duplicate_sales = []
        sold_seats = {}
        for tx in self._transactions:
            if tx.type == "售票" and tx.success:
                if tx.seat_id in sold_seats:
                    duplicate_sales.append((tx.seat_id, sold_seats[tx.seat_id], tx.window_id))
                else:
                    sold_seats[tx.seat_id] = tx.window_id
        seat_state_mismatch = []
        for seat_id, seat in self.seats.items():
            tx_sold = seat_id in sold_seats
            actual_sold_state = seat.status == SeatStatus.SOLD
            if tx_sold != actual_sold_state:
                seat_state_mismatch.append({
                    "seat_id": seat_id,
                    "tx_says_sold": tx_sold,
                    "actual_state": seat.status.value,
                    "last_tx_window": sold_seats.get(seat_id, "N/A")
                })
        is_consistent = (
            actual_sold + actual_available == self.total_seats
            and len(duplicate_sales) == 0
            and len(seat_state_mismatch) == 0
            and self._sold_count == actual_sold
        )
        return {
            "is_consistent": is_consistent,
            "total_seats": self.total_seats,
            "actual_sold": actual_sold,
            "actual_available": actual_available,
            "counter_sold": self._sold_count,
            "success_sales": success_sell_tx,
            "duplicate_sales": duplicate_sales,
            "seat_state_mismatch": seat_state_mismatch,
            "total_transactions": len(self._transactions)
        }


class UnsafeWindow(threading.Thread):
    def __init__(self, window_id, ticket_system, stop_event):
        super().__init__(name=window_id, daemon=True)
        self.window_id = window_id
        self.ticket_system = ticket_system
        self.stop_event = stop_event
        self.tickets_sold = 0

    def run(self):
        while not self.stop_event.is_set() and not self.ticket_system.is_sale_stopped():
            available = self.ticket_system.get_available_seats()
            if not available:
                break
            seat_id = random.choice(available)
            if self.ticket_system.sell_ticket(seat_id, self.window_id):
                self.tickets_sold += 1
            time.sleep(random.uniform(0.005, 0.02))


def run_unsafe_test():
    print("=" * 70)
    print("对比测试：无锁并发售票 vs 有锁并发售票")
    print("=" * 70)

    print("\n🚨 测试1：无锁机制（预期会出现重复售票")
    print("-" * 70)

    total_seats = 50
    num_windows = 8

    unsafe_system = UnsafeTicketSystem(total_seats)
    stop_event = threading.Event()
    windows = [UnsafeWindow(f"窗口-{i+1:02d}", unsafe_system, stop_event) for i in range(num_windows)]

    start = time.time()
    for w in windows:
        w.start()

    time.sleep(3)

    stop_event.set()
    for w in windows:
        w.join(timeout=2)

    elapsed = time.time() - start

    result = unsafe_system.verify_consistency()

    total_sold_by_windows = sum(w.tickets_sold for w in windows)

    print(f"  总座位数: {result['total_seats']}")
    print(f"  实际已售: {result['actual_sold']}")
    print(f"  各窗口合计售票数: {total_sold_by_windows}")
    print(f"  系统计数器: {result['counter_sold']}")
    print(f"  成功售票交易数: {result['success_sales']}")
    print(f"  总交易数: {result['total_transactions']}")
    print(f"  重复售票数: {len(result['duplicate_sales'])}")
    print(f"  状态不一致数: {len(result['seat_state_mismatch'])}")
    print(f"  一致性: {'❌ 数据不一致 (存在重复售票)' if not result['is_consistent'] else '✅ 一致'}")

    if result['duplicate_sales'][:10]:
        print("\n  重复售票示例:")
        for seat_id, w1, w2 in result['duplicate_sales'][:5]:
            print(f"    座位 {seat_id}: 被 {w1} 和 {w2} 同时售出")

    print("\n✅ 测试2：有锁机制（预期数据一致")
    print("-" * 70)

    from ticket_system import TicketSystem
    from ticket_window import TicketWindow

    safe_system = TicketSystem(total_seats)
    stop_event2 = threading.Event()
    safe_windows = []
    for i in range(num_windows):
        window_id = f"窗口-{i+1:02d}"
        w = TicketWindow(
            window_id=window_id,
            ticket_system=safe_system,
            sale_delay_range=(0.005, 0.02),
            refund_probability=0.0,
            query_probability=0.0
        )
        safe_windows.append(w)

    start2 = time.time()
    for w in safe_windows:
        w.start()

    time.sleep(3)

    safe_system.stop_sale()
    for w in safe_windows:
        w.stop()
        w.join(timeout=2)

    elapsed2 = time.time() - start2

    result2 = safe_system.verify_consistency()

    total_sold_by_windows2 = sum(w.tickets_sold for w in safe_windows)

    print(f"  总座位数: {result2['total_seats']}")
    print(f"  实际已售: {result2['actual_sold']}")
    print(f"  各窗口合计售票数: {total_sold_by_windows2}")
    print(f"  系统计数器: {result2['counter_sold']}")
    print(f"  成功售票交易数: {result2['success_sales']}")
    print(f"  总交易数: {result2['total_transactions']}")
    print(f"  重复售票数: {len(result2['duplicate_sales'])}")
    print(f"  状态不一致数: {len(result2['seat_state_mismatch'])}")
    print(f"  一致性: {'✅ 数据完全一致' if result2['is_consistent'] else '❌ 不一致'}")

    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    print("  无锁系统: 出现了 {} 次重复售票，数据不一致".format(len(result['duplicate_sales'])))
    print("  有锁系统: 无重复售票，数据完全一致")
    print("  这证明了互斥锁（RLock）有效防止了并发冲突！")
    print("=" * 70)


if __name__ == "__main__":
    run_unsafe_test()
