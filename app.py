import streamlit as st
import json
import os
from datetime import date
import random
import base64
from openai import OpenAI

# ========== 数据存储 ==========
DATA_FILE = "records.json"


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(records):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ========== 科学计算 ==========
def calc_bmr(gender, weight, height, age):
    if gender == "男":
        return 10 * weight + 6.25 * height - 5 * age + 5
    else:
        return 10 * weight + 6.25 * height - 5 * age - 161


def calc_tdee(bmr, activity):
    factors = {
        "久坐(几乎不运动)": 1.2,
        "轻度(每周1-3次)": 1.375,
        "中度(每周3-5次)": 1.55,
        "高度(每周6-7次)": 1.725,
    }
    return bmr * factors[activity]


# ========== 动作库 ==========
EXERCISES = {
    "胸": ["标准俯卧撑 3组x10次", "上斜俯卧撑 3组x12次", "宽距俯卧撑 3组x10次"],
    "背": ["引体向上 3组x力竭", "哑铃划船 3组x12次", "超人式 3组x15次"],
    "腿": ["深蹲 3组x15次", "箭步蹲 3组x12次", "臀桥 3组x15次"],
    "核心": ["平板支撑 3组x45秒", "卷腹 3组x15次", "俄罗斯挺身 3组x20次"],
    "有氧": ["慢跑/快走 30分钟", "跳绳 15分钟", "跟着视频做Hiit 20分钟"]
}


def generate_plan(goal, days):
    plan = {}
    if goal == "减脂":
        if days <= 3:
            plan["周一"] = "全身燃脂：深蹲 + 俯卧撑 + 平板支撑 + 慢跑30分钟"
            plan["周三"] = "心肺提升：跳绳15分钟 + 箭步蹲 + 卷腹"
            plan["周五"] = "轻松有氧：快走或骑车40分钟"
        else:
            plan["周一"] = "全身基础：深蹲 + 俯卧撑 + 平板支撑"
            plan["周二"] = "有氧燃脂：慢跑30分钟 + 核心训练"
            plan["周四"] = "下肢强化：箭步蹲 + 臀桥 + 跳绳15分钟"
            plan["周六"] = "上肢+心肺：俯卧撑 + 哑铃划船 + Hiit 20分钟"
    else:
        plan["周一"] = "推类(胸/肩)：俯卧撑 + 哑铃卧推 + 平板支撑"
        plan["周三"] = "拉类(背/二头)：引体向上 + 哑铃划船 + 卷腹"
        plan["周五"] = "下肢(腿/臀)：深蹲 + 箭步蹲 + 臀桥"
    return plan


# ========== 科学建议 ==========
def give_advice(records):
    if len(records) < 2:
        return ["记录还不够，坚持打卡几天后我会给你分析趋势。"]
    advices = []
    weights = [r["weight"] for r in records]
    recent = weights[-7:]
    if len(recent) >= 3:
        change = recent[-1] - recent[0]
        weekly_change = change / (len(recent) - 1)
        if weekly_change < -1.0:
            advices.append("⚠️ 体重下降过快（每周超过1kg），可能掉肌肉，建议每天多吃200千卡。")
        elif weekly_change < -0.2:
            advices.append("✅ 减重速度很健康（每周0.2-1kg），继续保持。")
        elif weekly_change < 0.2:
            advices.append("😐 体重基本没变，建议检查是否吃超了，或增加运动量。")
        else:
            advices.append("⚠️ 体重在上升，需要减少摄入或增加消耗。")

    recent_deficit = [r["gap"] for r in records[-3:]]
    avg_deficit = sum(recent_deficit) / len(recent_deficit)

    if avg_deficit < 0:
        advices.append(f"🍔 最近三天平均吃超了{abs(round(avg_deficit))}千卡，建议减少主食和零食。")
    elif avg_deficit > 700:
        advices.append(f"⚠️ 最近缺口过大（{round(avg_deficit)}千卡），身体可能进入节能模式，建议多吃一点。")
    else:
        advices.append(f"✅ 最近三天平均缺口{round(avg_deficit)}千卡，在健康范围内。")
    return advices


# ========== 界面 ==========
st.set_page_config(page_title="减肥助手", page_icon="🥗")
st.title("🥗 我的减肥助手")

records = load_data()

# 侧边栏
with st.sidebar:
    st.header("个人信息")
    gender = st.selectbox("性别", ["男", "女"])
    height = st.number_input("身高(cm)", 100.0, 220.0, 170.0)
    age = st.number_input("年龄", 10, 80, 20)
    activity = st.selectbox("活动量", [
        "久坐(几乎不运动)", "轻度(每周1-3次)",
        "中度(每周3-5次)", "高度(每周6-7次)"
    ])

    st.divider()
    st.header("大模型设置")
    # 填入你的智谱 API Key
    try:
        # 优先从云端环境读取安全的 Key
        api_key = st.secrets["ZHIPU_API_KEY"]
    except:
        # 如果本地没有配置，就显示输入框让你手动填
        api_key = st.text_input("智谱 API Key", type="password")

# 选项卡
tab1, tab2 = st.tabs(["📝 每日打卡", "🏋️ 锻炼计划"])

# --------- 选项卡1：每日打卡 ---------
with tab1:
    st.subheader("今日打卡")

    weight = st.number_input("今日体重(kg)", 30.0, 200.0, 60.0, 0.1)

    # ==== 新增的图片识别区域 ====
    st.write("📷 **不知道吃了多少千卡？拍照让 AI 帮你算！**")
    uploaded_file = st.file_uploader("上传食物照片", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        st.image(uploaded_file, caption="已上传的照片", width=300)

        if st.button("🤖 识别这顿饭的热量"):
            if not api_key:
                st.error("请先在左侧边栏填入你的 API Key！")
            else:
                with st.spinner("AI 营养师正在仔细端详你的照片..."):
                    try:
                        # 1. 把图片转成 Base64 格式给 AI 看
                        img_bytes = uploaded_file.getvalue()
                        b64_img = base64.b64encode(img_bytes).decode('utf-8')

                        # 2. 配置智谱的接口
                        client = OpenAI(
                            api_key=api_key,
                            base_url="https://open.bigmodel.cn/api/paas/v4/"
                        )
                        # 3. 发请求，要求只返回 JSON
                        response = client.chat.completions.create(
                            model="glm-4v",  # 智谱的视觉模型
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text",
                                         "text": "你是一个营养师。请识别图片里的食物，估算总热量。只返回纯JSON格式，不要任何其他文字。格式：{\"food\": \"食物名称\", \"calories\": 估算的纯数字热量}"},
                                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                                    ]
                                }
                            ]
                        )

                        # 4. 解析 AI 的回复
                        result_text = response.choices[0].message.content
                        # 清理一下多余的markdown符号
                        result_text = result_text.replace("```json", "").replace("```", "").strip()

                        import json as py_json

                        result_json = py_json.loads(result_text)

                        st.success(
                            f"识别成功！看起来是：**{result_json['food']}**，估算约 **{result_json['calories']} 千卡**。")
                        st.session_state['ai_calories'] = result_json['calories']

                    except Exception as e:
                        st.error(f"识别失败了，报错信息：{e}")

    # 摄入填写的默认值，如果是识别过的，就用识别结果
    default_intake = st.session_state.get('ai_calories', 1500.0)
    intake = st.number_input("今日摄入(千卡) - (可手动修改)", 0.0, 5000.0, float(default_intake), 10.0)
    note = st.text_input("今天吃了什么/运动了什么（可选）")

    if st.button("确认打卡"):
        bmr = calc_bmr(gender, weight, height, age)
        tdee = calc_tdee(bmr, activity)
        gap = tdee - intake

        records.append({
            "date": str(date.today()),
            "weight": weight,
            "intake": intake,
            "bmr": round(bmr),
            "tdee": round(tdee),
            "gap": round(gap),
            "note": note,
        })
        save_data(records)
        # 打卡完清空暂存的AI数据
        if 'ai_calories' in st.session_state:
            del st.session_state['ai_calories']

        st.success(f"打卡成功！今日热量缺口：{round(gap)} 千卡")
        st.rerun()

    if records:
        st.subheader("📊 历史记录")
        st.table(records[-10:])
        st.subheader("📈 体重趋势")
        st.line_chart([r["weight"] for r in records])
        st.subheader("💡 科学建议")
        for a in give_advice(records):
            st.write(a)

# --------- 选项卡2：锻炼计划 ---------
with tab2:
    st.subheader("定制你的专属练法")
    col1, col2 = st.columns(2)
    with col1:
        goal = st.radio("你的主要目标", ["减脂", "增肌/塑形"])
    with col2:
        days = st.slider("每周能练几天？", 2, 6, 3)

    st.write("---")
    st.write(f"为你生成的一周课表（目标：{goal}，每周{days}练）：")
    weekly_plan = generate_plan(goal, days)
    for day, workout in weekly_plan.items():
        st.info(f"**{day}**：{workout}")

    st.write("---")
    st.write("### 🎲 今天不知道练啥？")
    if st.button("帮我抽随机训练"):
        selected = random.sample(list(EXERCISES.keys()), 3)
        for body_part in selected:
            st.success(f"**{body_part}**：{random.choice(EXERCISES[body_part])}")
