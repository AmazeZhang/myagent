# app.py
import streamlit as st
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from core.core import ManusCore
from tools.document_reader import DocumentReaderTool
from tools.web_tools_collection import WebToolsCollection
from utils.file_utils import save_upload
from utils.parser_utils import parse_file, get_preview
from utils.config_manager import config_manager

st.set_page_config(page_title="OpenManus-LC", layout="wide")


@st.cache_resource
# 修改模型初始化函数，支持模型类型选择
def init_core(model_name=None, model_type="ollama"):
    if "core" not in st.session_state or st.session_state.get("current_model") != f"{model_type}:{model_name}":
        # 保存当前模型信息到session state
        st.session_state.current_model = f"{model_type}:{model_name}"
        
        # 根据模型类型设置环境变量（如果需要）
        if model_type == "openrouter":
            os.environ["MODEL_NAME"] = model_name
        else:
            os.environ["OLLAMA_MODEL"] = model_name
        
        # 创建核心实例
        # 修改ManusCore初始化，传递model_type参数
        core = ManusCore(model_name=model_name, model_type=model_type)
        
        # 注册基础工具
        core.register_tool(DocumentReaderTool(memory=core.doc_memory))
        #core.register_tool(BaiduSearchTool())

        # 注册网页工具集合 - 修复：创建实例后调用方法
        web_tools_collection = WebToolsCollection()
        web_tools = web_tools_collection.get_all_tools()
        for tool in web_tools:
            core.register_tool(tool)

        # 删除重复的视觉工具集合注册
        # for vision_tool in VisionToolsCollection.get_all_tools(memory=core.doc_memory):
        #     core.register_tool(vision_tool)

        core.build_agent()
        st.session_state.core = core
    return st.session_state.core


# 添加模型选择下拉框
with st.sidebar:
    st.title("⚙️ 配置")
    
    # 首先选择模型类型
    model_type = st.selectbox(
        "选择模型类型",
        ["ollama", "openrouter"],
        index=0
    )
    
    # 根据模型类型显示不同的模型选项
    if model_type == "ollama":
        model_name = st.selectbox(
            "选择 Ollama 模型",
            ["qwen3:14b", "llama3", "gemma:7b", "mistral", "自定义..."],
            index=0
        )
        
        # 如果选择自定义，则让用户输入模型名
        if model_name == "自定义...":
            model_name = st.text_input("输入 Ollama 模型名称", value="")
    else:  # openrouter
        model_name = st.selectbox(
            "选择 OpenRouter 模型",
            ["x-ai/grok-4.1-fast:free", "自定义..."],
            index=0
        )
        
        # 如果选择自定义，则让用户输入模型名
        if model_name == "自定义...":
            model_name = st.text_input("输入 OpenRouter 模型名称", value="deepseek/deepseek-r1-0528:free")
    
    # 显示OpenRouter API密钥配置提示
    if model_type == "openrouter" and not config_manager.openrouter_api_key:
        st.warning("⚠️ OpenRouter API密钥未配置，请在.env文件中设置OPENROUTER_API_KEY")

# 初始化核心，传入模型类型和名称
manus = init_core(model_name=model_name, model_type=model_type)
st.title("📖 OpenManus-LC (LangChain + 多模型 + Streamlit)")
st.markdown("---")

# 添加工具使用说明
with st.expander("💡 工具使用指南"):
    st.markdown("""
    ### 网页搜索工具
    `web_search query="搜索关键词" [, engine="baidu/google/bing"] [, num=5]`
    
    ### 网页内容提取工具
    `web_extractor url="网页URL" [, extract="all/title/text/links/images"] [, max_chars=2000]`
    
    ### 网页截图工具（增强版）
    `web_screenshot url="网页URL" [, width=1280] [, height=800] [, analyze_with_vlm=true/false] [, vlm_prompt="分析提示"]`
    
    ### VLM图像分析工具
    `vlm_analysis image_base64="base64编码的图像数据" [, prompt="分析提示"] [, model="gemma3:12b"]`
    
    ### 网页下载工具
    `web_download url="下载链接" [, filename="保存文件名"] [, save_path="保存路径"]`
    
    ### 网页交互工具
    `web_interaction action="create_session" url="网页URL"`
    `web_interaction action="click" session_id="会话ID" selector="元素选择器"`
    `web_interaction action="fill_form" session_id="会话ID" params={"form_data":{"选择器":"值"}}`
    `web_interaction action="close_session" session_id="会话ID"`
    """)

# ========== 上传文档部分 ==========
uploaded_file = st.file_uploader("📂 上传文档", type=["txt", "pdf", "docx", "md"], key="file_uploader")

# 检查是否已经处理过当前文件
if uploaded_file is not None:
    # 检查是否已经处理过相同的文件
    file_hash = f"{uploaded_file.name}_{uploaded_file.size}"
    if "last_uploaded_file" not in st.session_state:
        st.session_state.last_uploaded_file = None
    
    # 如果文件与上次相同，跳过重复处理
    if st.session_state.last_uploaded_file == file_hash:
        st.info("📄 文档已上传，可直接使用文档ID进行查询")
    else:
        # 处理新文件
        st.session_state.last_uploaded_file = file_hash
        
        # 正确解包返回值
        doc_id, path = save_upload(uploaded_file)
        text = parse_file(path)
        preview = get_preview(text)
        
        # 检查是否已经存在相同内容的文档
        existing_doc_id = None
        for doc_id_existing, doc_info in manus.doc_memory.documents.items():
            if doc_info.get("name") == uploaded_file.name and doc_info.get("path") == path:
                existing_doc_id = doc_id_existing
                break
        
        if existing_doc_id:
            st.success(f"✅ 文档已存在：{uploaded_file.name}（ID: {existing_doc_id}）")
            doc_id = existing_doc_id
        else:
            # 添加新文档到记忆
            new_doc_id = manus.doc_memory.add_document(path, name=uploaded_file.name, preview=preview, full_text_snippet=text[:10000])
            st.success(f"✅ 已上传文档：{uploaded_file.name}（ID: {new_doc_id}）")
            doc_id = new_doc_id
        
        st.text_area("内容预览：", preview, height=150)
        
        # 保存当前文档ID到session state
        st.session_state.current_doc_id = doc_id

# 显示当前可用的文档列表
if hasattr(manus.doc_memory, 'documents') and manus.doc_memory.documents:
    with st.expander("📋 可用文档列表"):
        for doc_id, doc_info in manus.doc_memory.documents.items():
            st.write(f"**ID**: {doc_id} | **名称**: {doc_info.get('name', '未知')}")
st.markdown("---")



# ========== 聊天部分 ==========
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("输入你的问题...")
if user_input:
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            # 获取包含思考过程的完整结果
            result = manus.run(user_input)

            # 无条件显示思考过程，不再需要用户点击展开
            st.subheader("🔍 智能专家选择与思考过程")

            # 显示使用的专家和描述
            expert_name = result.get('expert_name', '未知专家')
            expert_description = result.get('expert_description', '无描述')
            st.markdown(f"**🤖 选择的专家**: {expert_name}")
            st.markdown(f"**📋 专家专长**: {expert_description}")

            # 显示性能统计（如果有）
            if result.get('performance_stats'):
                stats = result['performance_stats']
                total = stats.get('total', 0)
                success = stats.get('success', 0)
                if total > 0:
                    success_rate = success / total
                    st.markdown(f"**📊 专家表现**: 成功率 {success_rate:.1%} (成功 {success}/总 {total})")

            # 显示是否使用了后备专家
            if result.get('backup_used'):
                st.info("⚠️ 使用了后备专家（原专家表现不佳）")

            # 显示Agent思考
            if result.get("llm_thoughts", ""):
                st.markdown(f"**💭 思考过程**: {result['llm_thoughts']}")

            # 显示计划（如果有）
            if result.get("plan", []):
                st.markdown("**📋 执行计划**: ")
                for i, step in enumerate(result['plan'], 1):
                    tool_name = step.get("tool", "未知工具")
                    tool_input = step.get("input", "")
                    st.markdown(f"  {i}. {tool_name}: {tool_input}")

            # 显示工具执行日志（如果有）
            if result.get("tool_logs", []):
                st.markdown("**🔧 工具执行日志**: ")
                for log in result['tool_logs']:
                    st.markdown(
                        f"  \n**步骤 {log['step']}**: {log['tool']}\n**输入**: {log['input']}\n**输出**: {log['output'][:200]}...")

            # 显示最终答案
            st.subheader("✅ 最终答案")
            st.write(result["final_answer"])

            # 显示成功评估
            success_eval = result.get('success_evaluation', False)
            if success_eval:
                st.success("✅ 回答质量评估: 良好")
            else:
                st.warning("⚠️ 回答质量评估: 需要改进")

    # 保存最终答案到消息历史
    st.session_state.messages.append({"role": "assistant", "content": result["final_answer"]})