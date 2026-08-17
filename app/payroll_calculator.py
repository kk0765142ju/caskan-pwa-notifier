import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class PayrollCalculator:
    """
    aroma Rilith 正式料金・給与計算エンジン
    
    【Bコース(ラグジュアリーコース等)計算規定】:
    ・コース代金から 4,000円 (70分は3,000円) をオプション料(全額スタッフ給与)として除外
    ・残りの基礎売上に歩合率 (50%〜70%) をかけてコースバックを計算
    ・最終受給給与 ＝ コースバック + オプション料 (4,000/3,000円) + 指名料バック - 割引負担
    """

    PAYROLL_TABLE = {
        18000: { 50: 9000,  55: 9500,  60: 10500, 65: 11500, 70: 12500 }, # 75分仰
        14000: { 50: 7000,  55: 7500,  60: 8000,  65: 9000,  70: 9500  }, # 70分
        17000: { 50: 8500,  55: 9000,  60: 10000, 65: 11000, 70: 11500 }, # 80分
        19000: { 50: 9500,  55: 10000, 60: 11000, 65: 12000, 70: 13000 }, # 90分
        21000: { 50: 10500, 55: 11000, 60: 12000, 65: 13000, 70: 14000 },
        22000: { 50: 11000, 55: 12000, 60: 13000, 65: 14000, 70: 15000 }, # 100分
        24000: { 50: 12000, 55: 13000, 60: 14000, 65: 15000, 70: 16000 }, # 120分
        30000: { 50: 15000, 55: 16500, 60: 18000, 65: 19500, 70: 21000 }, # 150分
        6000:  { 50: 3000,  55: 3000,  60: 3500,  65: 3500,  70: 4000  }, # 延長20分
    }

    @classmethod
    def get_slide_rate(cls, hon_shimei_count: int, is_fixed_salary: bool = False) -> int:
        if is_fixed_salary:
            return 50
        if hon_shimei_count >= 4:
            return 70
        elif hon_shimei_count == 3:
            return 65
        elif hon_shimei_count == 2:
            return 60
        elif hon_shimei_count == 1:
            return 55
        else:
            return 50

    @classmethod
    def calculate_reservation_back(cls, res: Dict[str, Any], slide_rate: int = 0) -> Dict[str, Any]:
        price = res.get("price", 0)
        shimei_type = res.get("shimei_type", "指名なし")
        course_name = res.get("course_name", "")
        
        # Bコース (ラグジュアリー / B付き) の判定
        is_b_course = res.get("is_luxury", False) or "ラグジュアリー" in course_name or "b" in course_name.lower()

        # 歩合率の適用
        mrate = slide_rate
        if mrate == 0 or mrate is None:
            mrate = res.get("margin_rate", 50)
            if mrate == 0:
                mrate = 50

        # ★ Bコース計算ロジック ★
        # コース代金から 4,000円 (70分は3,000円) を控除した「基礎売上」に歩合率をかける
        option_fee = 0
        base_course_price = price

        if is_b_course:
            option_fee = 3000 if "70分" in course_name else 4000
            # キャスカン上の生オプションバックがあればそれを使用
            c_opt = res.get("cast_margin_option", 0)
            if c_opt > 0:
                option_fee = c_opt
            base_course_price = max(0, price - option_fee)

        # 基礎売上に対するコースバック計算
        course_back = 0
        if base_course_price in cls.PAYROLL_TABLE:
            course_back = cls.PAYROLL_TABLE[base_course_price].get(mrate, int(base_course_price * (mrate / 100)))
        else:
            course_back = int(base_course_price * (mrate / 100))

        # 指名バック
        nominate_back = res.get("cast_margin_nominate", 0)
        if nominate_back == 0 and ("本指名" in shimei_type or "写真指名" in shimei_type):
            nominate_back = 2000

        # セラピスト割引負担
        disc_back = res.get("cast_margin_discount", 0)

        # 最終受給給与 ＝ コースバック (基礎売上×歩合) + オプション100%バック + 指名バック - 割引負担
        total_back = (course_back + option_fee + nominate_back) - disc_back
        shop_net = price - total_back

        return {
            "rate_used": mrate,
            "is_b_course": is_b_course,
            "base_course_price": base_course_price,
            "course_back": course_back,
            "option_fee": option_fee,
            "nominate_back": nominate_back,
            "disc_back": disc_back,
            "total_back": total_back,
            "shop_net": shop_net
        }

    @classmethod
    def calculate_daily_summary(cls, reservations: List[Dict[str, Any]], is_fixed_salary: bool = False, is_discount_exempt: bool = False) -> Dict[str, Any]:
        hon_shimei_count = 0
        for r in reservations:
            stype = r.get("shimei_type", "")
            if "本指名" in stype:
                hon_shimei_count += 1

        slide_rate = cls.get_slide_rate(hon_shimei_count, is_fixed_salary)
        
        total_list_price = 0
        total_therapist_pay = 0
        calc_reservations = []

        for r in reservations:
            res_rate = r.get("margin_rate", slide_rate)
            if res_rate == 0:
                res_rate = slide_rate

            b_info = cls.calculate_reservation_back(r, res_rate)
            total_list_price += r.get("price", 0)
            total_therapist_pay += b_info["total_back"]

            r_calc = dict(r)
            r_calc["margin_rate"] = b_info["rate_used"]
            r_calc["calculated_course_back"] = b_info["course_back"]
            r_calc["calculated_luxury_bonus"] = b_info["option_fee"]
            r_calc["calculated_nominate_back"] = b_info["nominate_back"]
            r_calc["therapist_net_pay"] = b_info["total_back"]
            r_calc["shop_net_revenue"] = b_info["shop_net"]
            calc_reservations.append(r_calc)

        total_shop_net_revenue = total_list_price - total_therapist_pay

        return {
            "hon_shimei_count": hon_shimei_count,
            "slide_rate": slide_rate,
            "total_reservations": len(reservations),
            "total_list_price": total_list_price,
            "total_therapist_net_pay": total_therapist_pay,
            "total_shop_net_revenue": total_shop_net_revenue,
            "reservations": calc_reservations
        }
