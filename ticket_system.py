import threading
import time
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict


class SeatStatus(Enum):
    AVAILABLE = "可用"
    SOLD = "已售"


@dataclass
class Seat:
    seat_id: int
    status: SeatStatus = SeatStatus.AVAILABLE
    sold_to: Optional[str] = None
    sold_time: Optional[float] = None


@dataclass
class Transaction:
    tx_id: int
    type: str
    seat_id: int
    window_id: str
    timestamp: float
    success: bool
    message: str = ""


class TicketSystem:
    def __init__(self, total_seats: int):
        self.total_seats = total_seats
        self.seats: Dict[int, Seat] = {i: Seat(seat_id=i) for i in range(1, total_seats + 1)}
        self._lock = threading.RLock()
        self._stop_sale = False
        self._transactions: List[Transaction] = []
        self._tx_counter = 0
        self._sold_count = 0
        self._refund_count = 0

    def _generate_tx_id(self) -> int:
        self._tx_counter += 1
        return self._tx_counter

    def _record_transaction(self, tx_type: str, seat_id: int, window_id: str,
                            success: bool, message: str = "") -> Transaction:
        tx = Transaction(
            tx_id=self._generate_tx_id(),
            type=tx_type,
            seat_id=seat_id,
            window_id=window_id,
            timestamp=time.time(),
            success=success,
            message=message
        )
        self._transactions.append(tx)
        return tx

    def stop_sale(self) -> None:
        with self._lock:
            self._stop_sale = True
            print(f"\n[系统] 收到停售指令，所有窗口即将停止售票")

    def is_sale_stopped(self) -> bool:
        with self._lock:
            return self._stop_sale

    def get_available_count(self) -> int:
        with self._lock:
            return sum(1 for s in self.seats.values() if s.status == SeatStatus.AVAILABLE)

    def get_sold_count(self) -> int:
        with self._lock:
            return self._sold_count

    def get_refund_count(self) -> int:
        with self._lock:
            return self._refund_count

    def get_available_seats(self) -> List[int]:
        with self._lock:
            return [s.seat_id for s in self.seats.values() if s.status == SeatStatus.AVAILABLE]

    def sell_ticket(self, seat_id: int, window_id: str) -> bool:
        with self._lock:
            if self._stop_sale:
                self._record_transaction("售票", seat_id, window_id, False, "已停售")
                return False

            if seat_id not in self.seats:
                self._record_transaction("售票", seat_id, window_id, False, "座位不存在")
                return False

            seat = self.seats[seat_id]
            if seat.status != SeatStatus.AVAILABLE:
                self._record_transaction("售票", seat_id, window_id, False, "座位已售出")
                return False

            seat.status = SeatStatus.SOLD
            seat.sold_to = window_id
            seat.sold_time = time.time()
            self._sold_count += 1
            self._record_transaction("售票", seat_id, window_id, True, "售票成功")
            return True

    def refund_ticket(self, seat_id: int, window_id: str) -> bool:
        with self._lock:
            if self._stop_sale:
                self._record_transaction("退票", seat_id, window_id, False, "已停售")
                return False

            if seat_id not in self.seats:
                self._record_transaction("退票", seat_id, window_id, False, "座位不存在")
                return False

            seat = self.seats[seat_id]
            if seat.status != SeatStatus.SOLD:
                self._record_transaction("退票", seat_id, window_id, False, "座位未售出")
                return False

            seat.status = SeatStatus.AVAILABLE
            seat.sold_to = None
            seat.sold_time = None
            self._refund_count += 1
            self._sold_count -= 1
            self._record_transaction("退票", seat_id, window_id, True, "退票成功")
            return True

    def get_sold_seats_by_window(self, window_id: str) -> List[int]:
        with self._lock:
            return [s.seat_id for s in self.seats.values()
                    if s.status == SeatStatus.SOLD and s.sold_to == window_id]

    def verify_consistency(self) -> dict:
        with self._lock:
            actual_sold = sum(1 for s in self.seats.values() if s.status == SeatStatus.SOLD)
            actual_available = sum(1 for s in self.seats.values() if s.status == SeatStatus.AVAILABLE)

            success_sell_tx = sum(1 for tx in self._transactions
                                  if tx.type == "售票" and tx.success)
            success_refund_tx = sum(1 for tx in self._transactions
                                    if tx.type == "退票" and tx.success)

            expected_sold = success_sell_tx - success_refund_tx
            expected_available = self.total_seats - expected_sold

            duplicate_sales = []
            seat_last_owner: Dict[int, Optional[str]] = {i: None for i in self.seats}
            simulated_sold_count = 0

            sorted_txs = sorted(self._transactions, key=lambda tx: (tx.timestamp, tx.tx_id))
            for tx in sorted_txs:
                if not tx.success:
                    continue

                if tx.type == "售票":
                    if seat_last_owner[tx.seat_id] is not None:
                        duplicate_sales.append((
                            tx.seat_id,
                            seat_last_owner[tx.seat_id],
                            tx.window_id,
                            tx.tx_id
                        ))
                    else:
                        seat_last_owner[tx.seat_id] = tx.window_id
                        simulated_sold_count += 1
                elif tx.type == "退票":
                    if seat_last_owner[tx.seat_id] is None:
                        duplicate_sales.append((
                            tx.seat_id,
                            "无",
                            tx.window_id,
                            tx.tx_id
                        ))
                    else:
                        seat_last_owner[tx.seat_id] = None
                        simulated_sold_count -= 1

            seat_state_mismatch = []
            for seat_id, seat in self.seats.items():
                tx_sold = seat_last_owner.get(seat_id) is not None
                actual_sold_state = seat.status == SeatStatus.SOLD
                if tx_sold != actual_sold_state:
                    seat_state_mismatch.append({
                        "seat_id": seat_id,
                        "tx_says_sold": tx_sold,
                        "actual_state": seat.status.value,
                        "last_tx_window": seat_last_owner.get(seat_id, "N/A")
                    })

            simulation_match = simulated_sold_count == actual_sold

            is_consistent = (
                actual_sold == expected_sold
                and actual_available == expected_available
                and actual_sold + actual_available == self.total_seats
                and len(duplicate_sales) == 0
                and len(seat_state_mismatch) == 0
                and self._sold_count == actual_sold
                and simulation_match
            )

            return {
                "is_consistent": is_consistent,
                "total_seats": self.total_seats,
                "actual_sold": actual_sold,
                "actual_available": actual_available,
                "expected_sold": expected_sold,
                "expected_available": expected_available,
                "counter_sold": self._sold_count,
                "counter_refund": self._refund_count,
                "total_transactions": len(self._transactions),
                "success_sales": success_sell_tx,
                "success_refunds": success_refund_tx,
                "duplicate_sales": duplicate_sales,
                "seat_state_mismatch": seat_state_mismatch,
                "total_seats_check": actual_sold + actual_available == self.total_seats,
                "counter_match": self._sold_count == actual_sold,
                "simulation_match": simulation_match,
                "simulated_sold_count": simulated_sold_count
            }

    def print_transaction_summary(self) -> None:
        with self._lock:
            window_stats: Dict[str, Dict] = {}
            for tx in self._transactions:
                if tx.window_id not in window_stats:
                    window_stats[tx.window_id] = {"sales": 0, "refunds": 0, "failures": 0}
                if tx.success:
                    if tx.type == "售票":
                        window_stats[tx.window_id]["sales"] += 1
                    elif tx.type == "退票":
                        window_stats[tx.window_id]["refunds"] += 1
                else:
                    window_stats[tx.window_id]["failures"] += 1

            print("\n" + "=" * 60)
            print("各窗口交易统计")
            print("=" * 60)
            for window_id, stats in sorted(window_stats.items()):
                print(f"  {window_id}: 售票 {stats['sales']} 张, 退票 {stats['refunds']} 张, 失败 {stats['failures']} 次")

    def get_transactions(self) -> List[Transaction]:
        with self._lock:
            return self._transactions.copy()
