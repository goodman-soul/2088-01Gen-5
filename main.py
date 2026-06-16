import time
import sys
from ticket_system import TicketSystem
from ticket_window import TicketWindow


def run_experiment(total_seats: int = 100, num_windows: int = 5,
                   run_seconds: int = 10, refund_prob: float = 0.05,
                   query_prob: float = 0.1, stop_before_sold_out: bool = True) -> dict:
    print("=" * 70)
    print("多窗口售票一致性实验")
    print("=" * 70)
    print(f"配置: {total_seats} 个座位, {num_windows} 个售票窗口, 运行 {run_seconds} 秒")
    print(f"      退票概率: {refund_prob*100:.0f}%, 查询概率: {query_prob*100:.0f}%")
    print(f"      停售模式: {'运行时间到后停售' if stop_before_sold_out else '售完为止'}")
    print("=" * 70)

    ticket_system = TicketSystem(total_seats)
    windows = []

    for i in range(num_windows):
        window_id = f"窗口-{i+1:02d}"
        window = TicketWindow(
            window_id=window_id,
            ticket_system=ticket_system,
            sale_delay_range=(0.005, 0.05),
            refund_probability=refund_prob,
            query_probability=query_prob
        )
        windows.append(window)

    start_time = time.time()

    print("\n[系统] 启动所有售票窗口...")
    for window in windows:
        window.start()

    print(f"[系统] 所有窗口已启动，开始计时 ({run_seconds} 秒)...\n")

    if stop_before_sold_out:
        time.sleep(run_seconds)
        ticket_system.stop_sale()
    else:
        while ticket_system.get_available_count() > 0 and not ticket_system.is_sale_stopped():
            time.sleep(0.1)
            elapsed = time.time() - start_time
            if elapsed >= run_seconds:
                ticket_system.stop_sale()
                break

    print("\n[系统] 等待所有窗口完成当前操作...")
    for window in windows:
        window.stop()
        window.join(timeout=2)

    end_time = time.time()
    elapsed = end_time - start_time

    print(f"\n[系统] 实验完成，总耗时 {elapsed:.2f} 秒")

    print("\n" + "=" * 70)
    print("各窗口销售汇总")
    print("=" * 70)
    total_sold_by_windows = 0
    total_refunded_by_windows = 0
    total_queries = 0
    for window in windows:
        print(f"  {window.window_id}: 售票 {window.tickets_sold} 张, 退票 {window.tickets_refunded} 张, 查询 {window.queries_performed} 次")
        total_sold_by_windows += window.tickets_sold
        total_refunded_by_windows += window.tickets_refunded
        total_queries += window.queries_performed
    print(f"  {'合计':>8}: 售票 {total_sold_by_windows} 张, 退票 {total_refunded_by_windows} 张, 查询 {total_queries} 次")

    ticket_system.print_transaction_summary()

    print("\n" + "=" * 70)
    print("账面一致性校验")
    print("=" * 70)

    result = ticket_system.verify_consistency()

    print(f"  总座位数:           {result['total_seats']}")
    print(f"  实际已售座位数:     {result['actual_sold']}")
    print(f"  实际可用座位数:     {result['actual_available']}")
    print(f"  账面应售座位数:     {result['expected_sold']}")
    print(f"  账面应余座位数:     {result['expected_available']}")
    print(f"  交易模拟售票数:     {result['simulated_sold_count']}")
    print(f"  系统售票计数器:     {result['counter_sold']}")
    print(f"  系统退票计数器:     {result['counter_refund']}")
    print(f"  成功售票交易数:     {result['success_sales']}")
    print(f"  成功退票交易数:     {result['success_refunds']}")
    print(f"  总交易记录数:       {result['total_transactions']}")
    print()
    print(f"  座位总数校验:       {'✅ 通过' if result['total_seats_check'] else '❌ 失败'} "
          f"({result['actual_sold']} + {result['actual_available']} = {result['actual_sold'] + result['actual_available']})")
    print(f"  计数器匹配校验:     {'✅ 通过' if result['counter_match'] else '❌ 失败'} "
          f"(计数器 {result['counter_sold']} == 实际 {result['actual_sold']})")
    print(f"  销售账面校验:       {'✅ 通过' if result['actual_sold'] == result['expected_sold'] else '❌ 失败'} "
          f"(实际 {result['actual_sold']} == 账面 {result['expected_sold']})")
    print(f"  余票账面校验:       {'✅ 通过' if result['actual_available'] == result['expected_available'] else '❌ 失败'} "
          f"(实际 {result['actual_available']} == 账面 {result['expected_available']})")
    print(f"  交易模拟校验:       {'✅ 通过' if result['simulation_match'] else '❌ 失败'} "
          f"(模拟 {result['simulated_sold_count']} == 实际 {result['actual_sold']})")
    print(f"  重复售票检测:       {'✅ 通过' if len(result['duplicate_sales']) == 0 else '❌ 失败'} "
          f"({len(result['duplicate_sales'])} 笔异常)")
    print(f"  座位状态一致性:     {'✅ 通过' if len(result['seat_state_mismatch']) == 0 else '❌ 失败'} "
          f"({len(result['seat_state_mismatch'])} 个座位状态不符)")
    print()
    print(f"  最终一致性结论:     {'✅ 数据完全一致' if result['is_consistent'] else '❌ 数据不一致'}")
    print("=" * 70)

    if result['duplicate_sales']:
        print("\n警告：检测到异常交易！")
        for item in result['duplicate_sales']:
            if len(item) == 4:
                seat_id, prev_owner, window, tx_id = item
                if prev_owner == "无":
                    print(f"  座位 {seat_id}: {window} 尝试退票但座位未售出 (交易#{tx_id})")
                else:
                    print(f"  座位 {seat_id}: 被 {prev_owner} 持有，{window} 重复售票 (交易#{tx_id})")
            else:
                seat_id, window1, window2 = item
                print(f"  座位 {seat_id}: 被 {window1} 和 {window2} 同时售出")

    if result['seat_state_mismatch']:
        print("\n警告：检测到座位状态不一致！")
        for mismatch in result['seat_state_mismatch']:
            print(f"  座位 {mismatch['seat_id']}: 交易记录显示"
                  f"{'已售' if mismatch['tx_says_sold'] else '未售'}, "
                  f"实际状态为 {mismatch['actual_state']}")

    if not result['is_consistent']:
        print("\n" + "!" * 70)
        print("一致性校验失败！并发控制存在问题。")
        print("!" * 70)

    result['elapsed_time'] = elapsed
    result['total_sold_by_windows'] = total_sold_by_windows
    result['total_refunded_by_windows'] = total_refunded_by_windows
    result['total_queries'] = total_queries

    return result


def main():
    print("\n" + "=" * 70)
    print("实验 1: 高并发短时间运行（测试快速抢票场景）")
    print("=" * 70)
    result1 = run_experiment(
        total_seats=50,
        num_windows=5,
        run_seconds=5,
        refund_prob=0.02,
        query_prob=0.05,
        stop_before_sold_out=True
    )

    print("\n\n" + "=" * 70)
    print("实验 2: 长时间运行含退票（测试复杂场景一致性）")
    print("=" * 70)
    result2 = run_experiment(
        total_seats=100,
        num_windows=8,
        run_seconds=10,
        refund_prob=0.08,
        query_prob=0.12,
        stop_before_sold_out=True
    )

    print("\n\n" + "=" * 70)
    print("实验 3: 售完为止模式（测试自然售罄场景）")
    print("=" * 70)
    result3 = run_experiment(
        total_seats=30,
        num_windows=6,
        run_seconds=30,
        refund_prob=0.03,
        query_prob=0.08,
        stop_before_sold_out=False
    )

    print("\n\n" + "=" * 70)
    print("实验总结")
    print("=" * 70)
    all_passed = result1['is_consistent'] and result2['is_consistent'] and result3['is_consistent']

    experiments = [
        ("实验1 (高并发抢票)", result1),
        ("实验2 (含退票场景)", result2),
        ("实验3 (售完为止)", result3),
    ]

    for name, res in experiments:
        status = "✅ 通过" if res['is_consistent'] else "❌ 失败"
        print(f"  {name}: {status} (交易 {res['total_transactions']} 次, 售票 {res['success_sales']} 张)")

    print()
    if all_passed:
        print("🎉 所有实验通过！多窗口售票一致性得到验证。")
        print("   锁机制有效防止了重复售票，退票和查询也保持了数据一致性。")
        return 0
    else:
        print("⚠️  部分实验失败，需要检查并发控制逻辑。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
