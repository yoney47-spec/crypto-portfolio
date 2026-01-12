"""
繝・せ繝医ョ繝ｼ繧ｿ逕滓・繧ｹ繧ｯ繝ｪ繝励ヨ
繝代ヵ繧ｩ繝ｼ繝槭Φ繧ｹ繝・せ繝育畑縺ｫ螟ｧ驥上・繝・Α繝ｼ繧ｹ繧堤函謌舌☆繧・
"""

import sqlite3
from datetime import datetime, timedelta
import random
from pathlib import Path

DB_PATH = Path(__file__).parent / "crypto_portfolio.db"

def generate_test_transactions(num_transactions=1000):
    """
    螟ｧ驥上・繝・せ繝亥叙蠑輔ョ繝ｼ繧ｿ繧堤函謌・
    
    Args:
        num_transactions: 逕滓・縺吶ｋ蜿門ｼ墓焚・医ョ繝輔か繝ｫ繝・ 1000莉ｶ・・
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 逋ｻ骭ｲ縺輔ｌ縺ｦ縺・ｋ雉・肇繧貞叙蠕・
        cursor.execute("SELECT id, symbol FROM assets")
        assets = cursor.fetchall()
        
        if not assets:
            print("[ERROR] 雉・肇縺檎匳骭ｲ縺輔ｌ縺ｦ縺・∪縺帙ｓ縲ょ・縺ｫ雉・肇繧堤匳骭ｲ縺励※縺上□縺輔＞縲・)
            return
        
        asset_ids = [asset[0] for asset in assets]
        
        print(f"[INFO] {len(assets)}遞ｮ鬘槭・雉・肇縺ｫ蟇ｾ縺励※{num_transactions}莉ｶ縺ｮ蜿門ｼ輔ｒ逕滓・縺励∪縺・..")
        
        # 繝・せ繝亥叙蠑輔ｒ逕滓・
        start_date = datetime(2020, 1, 1)
        transaction_types = ['Buy', 'Sell', 'Airdrop', 'Staking Reward', 'Interest', 'Gift']
        
        generated_count = 0
        
        for i in range(num_transactions):
            # 繝ｩ繝ｳ繝繝縺ｪ譌･譎ら函謌撰ｼ・020蟷ｴ・樒樟蝨ｨ・・
            days_offset = random.randint(0, 1460)  # 邏・蟷ｴ蛻・
            hours_offset = random.randint(0, 23)
            minutes_offset = random.randint(0, 59)
            
            trans_date = start_date + timedelta(
                days=days_offset,
                hours=hours_offset,
                minutes=minutes_offset
            )
            
            # 繝ｩ繝ｳ繝繝縺ｪ雉・肇驕ｸ謚・
            asset_id = random.choice(asset_ids)
            
            # 繝ｩ繝ｳ繝繝縺ｪ蜿門ｼ輔ち繧､繝・
            trans_type = random.choice(transaction_types)
            
            # 繝ｩ繝ｳ繝繝縺ｪ謨ｰ驥擾ｼ郁ｳ・肇縺ｫ繧医▲縺ｦ逡ｰ縺ｪ繧九せ繧ｱ繝ｼ繝ｫ・・
            if trans_type in ['Airdrop', 'Staking Reward', 'Interest', 'Gift']:
                # 繧ｳ繧ｹ繝医ぞ繝ｭ蜿門ｼ・
                quantity = random.uniform(0.01, 100)
                price = 0.0
            else:
                # Buy/Sell
                quantity = random.uniform(0.001, 10)
                # 迴ｾ螳溽噪縺ｪ萓｡譬ｼ遽・峇・・10 縲・$50,000・・
                price = random.uniform(10, 50000)
            
            total = quantity * price
            
            # 蜿門ｼ輔ｒ謖ｿ蜈･
            cursor.execute("""
                INSERT INTO transactions 
                (date, type, asset_id, quantity, price_per_unit, total_amount, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trans_date.strftime("%Y-%m-%d %H:%M:%S"),
                trans_type,
                asset_id,
                quantity,
                price,
                total,
                f"Test transaction #{i+1}"
            ))
            
            generated_count += 1
            
            # 騾ｲ謐苓｡ｨ遉ｺ
            if (i + 1) % 100 == 0:
                print(f"  騾ｲ謐・ {i+1}/{num_transactions} 莉ｶ逕滓・...")
        
        conn.commit()
        print(f"\n[SUCCESS] {generated_count}莉ｶ縺ｮ繝・せ繝亥叙蠑輔ｒ逕滓・縺励∪縺励◆・・)
        
        # 邨ｱ險域ュ蝣ｱ繧定｡ｨ遉ｺ
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total_transactions = cursor.fetchone()[0]
        print(f"[INFO] 繝・・繧ｿ繝吶・繧ｹ蜀・・邱丞叙蠑墓焚: {total_transactions}莉ｶ")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] 繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}")
    finally:
        conn.close()


def clear_test_transactions():
    """
    繝・せ繝亥叙蠑輔ョ繝ｼ繧ｿ繧偵け繝ｪ繧｢・域ｳｨ諢・ 謇句虚縺ｧ霑ｽ蜉縺励◆蜿門ｼ輔ｂ蜑企勁縺輔ｌ縺ｾ縺呻ｼ・
    """
    print("[WARNING] 縺吶∋縺ｦ縺ｮ蜿門ｼ輔ョ繝ｼ繧ｿ繧貞炎髯､縺励∪縺吶°・・)
    confirm = input("邯夊｡後☆繧九↓縺ｯ 'yes' 縺ｨ蜈･蜉帙＠縺ｦ縺上□縺輔＞: ")
    
    if confirm.lower() == 'yes':
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM transactions")
            conn.commit()
            print("[SUCCESS] 縺吶∋縺ｦ縺ｮ蜿門ｼ輔ョ繝ｼ繧ｿ繧貞炎髯､縺励∪縺励◆")
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] 蜑企勁縺ｫ螟ｱ謨励＠縺ｾ縺励◆: {str(e)}")
        finally:
            conn.close()
    else:
        print("[CANCELLED] 蜑企勁繧偵く繝｣繝ｳ繧ｻ繝ｫ縺励∪縺励◆")


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("繝・せ繝医ョ繝ｼ繧ｿ逕滓・繝・・繝ｫ")
    print("=" * 60)
    print()
    print("1. 繝・せ繝亥叙蠑輔ｒ逕滓・ (1000莉ｶ)")
    print("2. 繝・せ繝亥叙蠑輔ｒ逕滓・ (5000莉ｶ)")
    print("3. 繝・せ繝亥叙蠑輔ｒ逕滓・ (繧ｫ繧ｹ繧ｿ繝)")
    print("4. 縺吶∋縺ｦ縺ｮ蜿門ｼ輔ョ繝ｼ繧ｿ繧貞炎髯､")
    print("5. 邨ゆｺ・)
    print()
    
    choice = input("驕ｸ謚槭＠縺ｦ縺上□縺輔＞ (1-5): ")
    
    if choice == "1":
        generate_test_transactions(1000)
    elif choice == "2":
        generate_test_transactions(5000)
    elif choice == "3":
        try:
            num = int(input("逕滓・縺吶ｋ蜿門ｼ墓焚繧貞・蜉・ "))
            if num > 0:
                generate_test_transactions(num)
            else:
                print("[ERROR] 豁｣縺ｮ謨ｴ謨ｰ繧貞・蜉帙＠縺ｦ縺上□縺輔＞")
        except ValueError:
            print("[ERROR] 辟｡蜉ｹ縺ｪ蜈･蜉帙〒縺・)
    elif choice == "4":
        clear_test_transactions()
    elif choice == "5":
        print("邨ゆｺ・＠縺ｾ縺・)
    else:
        print("[ERROR] 辟｡蜉ｹ縺ｪ驕ｸ謚槭〒縺・)
