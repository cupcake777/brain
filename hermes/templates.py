"""HTML templates for Hermes review UI – dependency-free, mobile-first, dark theme."""

from __future__ import annotations
import json as _json
import os

import html as _html

# ── i18n translations ──────────────────────────────────────────────────────
_I18N_DICT = {
    "zh": {
        "nav_home": "首页", "nav_knowledge": "知识", "nav_gallery": "绘图", "nav_services": "服务",
        "nav_profile": "我的", "nav_label": "导航", "nav_user": "用户",
        "dash_greeting": "你好，探索者", "dash_total": "总节点", "dash_canonized": "正典",
        "dash_refined": "精炼", "dash_draft": "草稿", "dash_recent": "📋 最近更新",
        "dash_viewall": "查看全部 →", "dash_shortcuts": "⚡ 快捷入口",
        "dash_knowledge": "知识树", "dash_gallery": "绘图库", "dash_monitor": "监控台",
        "dash_tokens": "今日 Tokens", "dash_requests": "今日请求数", "dash_cost": "今日费用",
        "dash_week": "本周费用", "dash_total_tokens": "累计 Tokens", "dash_total_req": "累计请求数",
        "dash_users": "用户数", "dash_rpm": "RPM(请求/分)",
        "dash_monitor_title": "📊 服务监控", "dash_monitor_link": "打开 Uptime Kuma ↗",
        "dash_monitor_desc1": "全栈服务状态监控 · 历史可用性数据",
        "dash_monitor_desc2": "服务健康检查 JSON 接口",
        "dash_auth_notice": "联合登录", "dash_auth_notice2": "与本系统共享凭据",
        "pf_prefs": "显示偏好", "pf_prefs_desc": "自定义界面显示", "pf_name": "显示名称",
        "pf_name_ph": "你的名字", "pf_avatar": "头像链接", "pf_avatar_ph": "输入头像图片URL",
        "pf_avatar_upload": "上传图片", "pf_avatar_too_large": "图片不能超过 200KB",
        "pf_theme": "主题", "pf_theme_dark": "深色 Dracula", "pf_theme_light": "浅色 Light",
        "pf_lang": "语言", "pf_lang_zh": "中文", "pf_lang_en": "English",
        "pf_save": "保存偏好", "pf_password": "修改密码", "pf_password_desc": "更新你的登录密码",
        "pf_cur_pw": "当前密码", "pf_new_pw": "新密码", "pf_confirm_pw": "确认新密码",
        "pf_update_pw": "更新密码", "pf_system": "系统信息", "pf_system_desc": "运行状态概览",
        "pf_status_run": "正常运行", "pf_online": "在线",
        "pf_logout": "退出登录", "pf_logout_desc": "结束当前会话并返回登录页",
        "pf_saved": "偏好已保存", "pf_explorer": "探索者", "pf_brain_user": "Hermes Brain 用户",
        "pf_admin": "管理员",
        "pf_pw_wrong": "当前密码不正确", "pf_pw_mismatch": "两次输入的新密码不一致",
        "pf_pw_short": "密码至少6个字符", "pf_pw_updated": "密码已更新",
        "svc_title": "🔗 服务中心", "svc_desc": "所有外部服务运行在独立服务器上，点击卡片直接跳转",
        "svc_detecting": "检测中...", "svc_online": "在线", "svc_offline": "离线", "svc_unknown": "未知",
        "svc_n8n": "自动化工作流", "svc_n8n_desc": "可视化编排API与任务，连接500+服务",
        "svc_kuma": "服务监控", "svc_kuma_desc": "实时状态监控、告警通知与SLA追踪",
        "svc_files": "文件管理", "svc_files_desc": "浏览、上传与管理工作文件",
        "greeting_morning": "早上好", "greeting_afternoon": "下午好", "greeting_evening": "晚上好",
        "time_sun": "星期日", "time_mon": "星期一", "time_tue": "星期二", "time_wed": "星期三",
        "time_thu": "星期四", "time_fri": "星期五", "time_sat": "星期六",
        "time_just": "刚刚", "time_min_ago": "分钟前", "time_hr_ago": "小时前", "time_day_ago": "天前",
        "time_comma": "，", "time_day_suffix": "日",
        "time_jan": "1月", "time_feb": "2月", "time_mar": "3月", "time_apr": "4月", "time_may": "5月", "time_jun": "6月",
        "time_jul": "7月", "time_aug": "8月", "time_sep": "9月", "time_oct": "10月", "time_nov": "11月", "time_dec": "12月",
        "btn_edit": "✏️ 编辑", "btn_promote": "⬆ 晋级为精炼", "btn_deprecate": "🗑 废弃",
        "btn_approve_db": "存入记忆库", "btn_approve_export": "批准并同步导出",
        "btn_promote_export": "升级为同步导出", "btn_reject": "拒绝此提案",
        "stage_title": "Stage 生命周期",
        "stage_draft_short": "草稿", "stage_refined_short": "精炼", "stage_verified_short": "验证", "stage_canonized_short": "正典", "stage_deprecated_short": "废弃",
        "stage_all": "全部",
        "stage_draft": "原始知识条目。未经整理的observation或手动输入。3天无矛盾自动晋级Refined",
        "stage_refined": "Agent已整理的表述。去冗余、结构化完成，但尚未经事实核查。7天无矛盾自动晋级Canonize",
        "stage_verified": "经来源或用户确认的可信事实。手动Promote到达，确认后可继续晋级Canonize",
        "stage_canonized": "核心知识。高置信度，导出至KNOWLEDGE.md。",
        "stage_deprecated": "垃圾箱。过时、错误或被替代的知识。点击\"Empty Trash\"永久删除。",
        "stat_pending": "待审提案", "no_recent": "暂无最近活动",
        "col_status": "状态", "col_summary": "摘要", "col_time": "时间", "dash_no_activity": "暂无最近活动", "dash_no_summary": "无摘要",
        "rv_no_proposals": "当前视图无提案",
        "rv_search": "搜索提案…",
        "rv_review": "← 返回审核",
        "rv_observation": "观察记录", "rv_why_matters": "为何重要",
        "rv_suggested": "建议持久记忆", "rv_scope": "范围",
        "rv_evidence": "证据", "rv_summary": "摘要",
        "rv_project": "项目", "rv_category": "类别", "rv_risk": "风险",
        "rv_source": "来源", "rv_created": "创建时间", "rv_weight": "权重",
        "rv_confirm": "确认", "rv_cancel": "取消",
        "rv_rejected": "此提案已被拒绝。",
        "rv_approved_synced": "此提案已批准并同步。",
        "rv_superseded": "此提案已被更新版本替代。",
        "rv_all": "全部", "rv_pending": "待审", "rv_approved": "已批准", "rv_synced": "已同步",
        "rv_approve_db": "存入记忆库", "rv_approve_export": "批准并同步导出",
        "rv_promote_export": "升级为同步导出", "rv_reject": "拒绝此提案",
        "kn_title": "知识树", "kn_search": "搜索知识…", "kn_add": "+ 添加知识",
        "kn_export": "⬇ 导出MD", "kn_retrospect": "🔄 回顾",
        "kn_empty_trash": "🗑 清空回收站", "kn_no_nodes": "当前筛选条件下无知识节点。",
        "kn_nodes": "节点", "kn_all_cat": "所有类别", "kn_all_dom": "所有领域",
        "kn_stage_lifecycle": "Stage 生命周期",
        "kn_draft_desc": "原始知识条目。未经整理的observation或手动输入。3天无矛盾自动晋级Refined。",
        "kn_refined_desc": "Agent已整理的表述。去冗余、结构化完成，但尚未经事实核查。7天无矛盾自动晋级Canonized。",
        "kn_verified_desc": "经来源或用户确认的可信事实。手动Promote到达，确认后可继续晋级Canonized。",
        "kn_canonized_desc": "核心知识。高置信度，导出至KNOWLEDGE.md。",
        "kn_deprecated_desc": "垃圾箱。过时、错误或被替代的知识。点击\"Empty Trash\"永久删除。",
        "kn_confidence_formula": "Confidence = category_base + source_bonus + evidence×0.05(上限0.2) − corrections×0.1 + retrieval_bonus + time_bonus − age_penalty<br>Clamped [0.0, 1.0]，Retrospect自动重算。",
        "kn_close": "关闭", "kn_cancel": "取消", "kn_submit": "提交",
        "kn_content_label": "内容 *", "kn_content_ph": "输入知识内容…",
        "kn_source_label": "来源", "kn_source_ph": "如：对话、手动、观察",
        "kn_category_label": "类别", "kn_domain_label": "领域",
        "kd_summary": "摘要", "kd_confidence": "置信度", "kd_content": "内容",
        "kd_evidence": "证据", "kd_provenance": "来源链",
        "kd_relationships": "关联", "kd_thought_chain": "思维链时间线",
        "kd_no_relationships": "暂无关联",
        "kd_no_relationships_hint": "与父节点、子节点或矛盾节点的连接将显示在此。",
        "kd_no_evidence": "尚无证据记录",
        "kd_no_evidence_hint": "关联证据将在此显示。",
        "kd_no_thought": "暂无思维链记录",
        "kd_no_thought_hint": "随着知识演进，推理步骤和决策将记录在此。",
        "kd_parent": "父节点", "kd_child": "子节点", "kd_supersedes": "取代",
        "kd_superseded_by": "被取代", "kd_contradicts": "矛盾",
        "kd_merged_from": "合并自", "kd_contradicts_list": "矛盾于", "kd_verified_by": "验证者",
        "kd_none_yet": "暂无",
        "kd_edit": "✏️ 编辑", "kd_promote": "⬆ 晋级为", "kd_deprecate": "🗑 废弃",
        "kd_delete_perm": "🗑 永久删除", "kd_merge_into": "🔗 合并到",
        "kd_no_actions": "节点处于{stage}阶段 — 无可用操作。",
        "kd_back": "← 知识树",
        "kd_node_id": "节点ID", "kd_category": "类别", "kd_domain": "领域",
        "kd_stage": "阶段", "kd_operation": "操作", "kd_source_label": "来源",
        "kd_created": "创建时间", "kd_refined": "精炼时间", "kd_verified": "验证时间",
        "kd_deprecated": "废弃时间", "kd_retrievals": "检索次数", "kd_last_used": "最后使用",
        "kd_corrections": "修正次数", "kd_save": "保存", "kd_cancel": "取消",
        "kd_edit_title": "✏️ 编辑节点",
        "kd_decision": "决策", "kd_tl_confidence": "置信度",
        "gl_title": "Sci-Fig 绘图库",
        "gl_subtitle": "科研图表模板库 — 查看、审核与贡献",
        "gl_search": "搜索图表…", "gl_showing": "显示", "gl_of": "/",
        "gl_submit": "+ 提交", "gl_image_url": "图片链接",
        "gl_image_url_ph": "https://...", "gl_or_upload": "或上传",
        "gl_notes": "备注", "gl_notes_ph": "图表类型、论文来源、你喜欢什么…",
        "gl_submit_btn": "提交", "gl_interactive": "交互式图表",
        "gl_planned": "计划中",
        "gl_suggest": "✎ 建议", "gl_suggest_ph": "输入建议…",
        "gl_approve_btn": "✓ 批准",
        "kd_evidence": "EVIDENCE", "kd_provenance": "PROVENANCE",
        "kd_relationships": "RELATIONSHIPS", "kd_thought": "THOUGHT CHAIN TIMELINE",
        "kd_no_evidence": "No evidence recorded",
        "kd_no_evidence_hint": "Supporting evidence will appear here when linked.",
        "kd_no_rel": "No relationships",
        "kd_no_rel_hint": "Connections to parent, child, or contradictory nodes will appear here.",
        "kd_no_thought": "No thought chain entries",
        "kd_no_thought_hint": "Reasoning steps and decisions will be recorded here as this knowledge evolves.",
        "kd_none_yet": "None yet",
        "kh_actions": "Action", "kh_approve": "Approve", "kh_reject": "Reject",
        "login_title": "登录", "login_subtitle": "知识管理系统", "login_user": "用户名", "login_pass": "密码", "login_btn": "登录",
        "toast_added": "已添加", "toast_export_done": "导出完成", "toast_retrospect_done": "回顾完成",
        "toast_deleted": "已删除 {count} 个节点", "toast_done": "完成", "toast_node_updated": "节点已更新",
        "toast_error": "错误", "toast_network_error": "网络错误", "toast_copy_ok": "已复制", "toast_copy_fail": "复制失败",
        "toast_no_interactive": "暂无交互版本", "toast_approved": "已批准", "toast_rejected": "已拒绝",
        "toast_suggestion_saved": "建议已保存", "toast_suggestion_noted": "建议已记录",
        "toast_enter_suggestion": "请先输入建议", "toast_enter_palette_name": "请输入调色板名称",
        "toast_min_colors": "请输入至少3个有效十六进制颜色", "toast_palette_submitted": "调色板已提交，感谢！",
        "toast_figure_submitted": "图表已提交分析", "toast_upload_ok": "模板上传成功",
        "toast_upload_fail": "上传失败", "toast_enter_url_or_file": "请提供图片URL或上传文件",
        "confirm_empty_trash": "确定清空回收站？此操作不可撤消。",
        "confirm_delete_node": "确定永久删除此节点？",
    },
    "en": {
        "nav_home": "Home", "nav_knowledge": "Knowledge", "nav_gallery": "Gallery", "nav_services": "Services",
        "nav_profile": "Profile", "nav_label": "Navigation", "nav_user": "User",
        "dash_greeting": "Hello, Explorer", "dash_total": "Total Nodes", "dash_canonized": "Canonized",
        "dash_refined": "Refined", "dash_draft": "Draft", "dash_recent": "📋 Recent Updates",
        "dash_viewall": "View all →", "dash_shortcuts": "⚡ Quick Access",
        "dash_knowledge": "Knowledge Tree", "dash_gallery": "Gallery", "dash_monitor": "Dashboard",
        "dash_tokens": "Today Tokens", "dash_requests": "Today Requests", "dash_cost": "Today Cost",
        "dash_week": "Weekly Cost", "dash_total_tokens": "Total Tokens", "dash_total_req": "Total Requests",
        "dash_users": "Users", "dash_rpm": "RPM (req/min)",
        "dash_monitor_title": "📊 Service Monitor", "dash_monitor_link": "Open Uptime Kuma ↗",
        "dash_monitor_desc1": "Full-stack service status & historical availability",
        "dash_monitor_desc2": "Service health check JSON endpoint",
        "dash_auth_notice": "Shared authentication", "dash_auth_notice2": "credentials shared with this system",
        "pf_prefs": "Display Preferences", "pf_prefs_desc": "Customize the interface", "pf_name": "Display Name",
        "pf_name_ph": "Your name", "pf_avatar": "Avatar URL", "pf_avatar_ph": "Enter avatar image URL",
        "pf_avatar_upload": "Upload Image", "pf_avatar_too_large": "Image must not exceed 200KB",
        "pf_theme": "Theme", "pf_theme_dark": "Dark Dracula", "pf_theme_light": "Light",
        "pf_lang": "Language", "pf_lang_zh": "中文", "pf_lang_en": "English",
        "pf_save": "Save Preferences", "pf_password": "Change Password", "pf_password_desc": "Update your login password",
        "pf_cur_pw": "Current Password", "pf_new_pw": "New Password", "pf_confirm_pw": "Confirm New Password",
        "pf_update_pw": "Update Password", "pf_system": "System Info", "pf_system_desc": "Runtime status overview",
        "pf_status_run": "Running", "pf_online": "Online",
        "pf_logout": "Sign Out", "pf_logout_desc": "End current session and return to login page",
        "pf_saved": "Preferences saved", "pf_explorer": "Explorer", "pf_brain_user": "Hermes Brain User",
        "pf_admin": "Admin",
        "pf_pw_wrong": "Current password is incorrect", "pf_pw_mismatch": "New passwords don't match",
        "pf_pw_short": "Password must be at least 6 characters", "pf_pw_updated": "Password updated",
        "svc_title": "🔗 Service Center", "svc_desc": "All services run on independent servers. Click cards to navigate.",
        "svc_detecting": "Detecting...", "svc_online": "Online", "svc_offline": "Offline", "svc_unknown": "Unknown",
        "svc_n8n": "Automation Workflows", "svc_n8n_desc": "Visual API & task orchestration, 500+ integrations",
        "svc_kuma": "Service Monitoring", "svc_kuma_desc": "Real-time status monitoring, alerts & SLA tracking",
        "svc_files": "File Manager", "svc_files_desc": "Browse, upload & manage work files",
        "greeting_morning": "Good morning", "greeting_afternoon": "Good afternoon", "greeting_evening": "Good evening",
        "time_sun": "Sun", "time_mon": "Mon", "time_tue": "Tue", "time_wed": "Wed",
        "time_thu": "Thu", "time_fri": "Fri", "time_sat": "Sat",
        "time_just": "just now", "time_min_ago": " min ago", "time_hr_ago": " hr ago", "time_day_ago": " days ago",
        "time_comma": ", ", "time_day_suffix": "",
        "time_jan": "Jan", "time_feb": "Feb", "time_mar": "Mar", "time_apr": "Apr", "time_may": "May", "time_jun": "Jun",
        "time_jul": "Jul", "time_aug": "Aug", "time_sep": "Sep", "time_oct": "Oct", "time_nov": "Nov", "time_dec": "Dec",
        "btn_edit": "✏️ Edit", "btn_promote": "⬆ Promote", "btn_deprecate": "🗑 Deprecate",
        "btn_approve_db": "Approve to Memory", "btn_approve_export": "Approve & Export",
        "btn_promote_export": "Promote to Export", "btn_reject": "Reject",
        "stage_title": "Stage Lifecycle",
        "stage_draft_short": "Draft", "stage_refined_short": "Refined", "stage_verified_short": "Verified", "stage_canonized_short": "Canonized", "stage_deprecated_short": "Deprecated",
        "stage_all": "Total",
        "stage_draft": "Raw knowledge. Unprocessed observations or manual entries. Auto-promotes to Refined after 3 conflict-free days.",
        "stage_refined": "Agent-curated. De-duplicated & structured, but not yet fact-checked. Auto-promotes to Canonized after 7 conflict-free days.",
        "stage_verified": "Source/user-confirmed facts. Reached via manual Promote. Can proceed to Canonize.",
        "stage_canonized": "Core knowledge. High confidence, exported to KNOWLEDGE.md.",
        "stage_deprecated": "Trash bin. Outdated, incorrect, or superseded knowledge. \"Empty Trash\" for permanent deletion.",
        "stat_pending": "Pending Proposals", "no_recent": "No recent activity",
        "col_status": "Status", "col_summary": "Summary", "col_time": "Time", "dash_no_activity": "No recent activity", "dash_no_summary": "No summary",
        "rv_no_proposals": "No proposals in this view",
        "rv_search": "Search proposals…",
        "rv_review": "← Review",
        "rv_observation": "Observation", "rv_why_matters": "Why it matters",
        "rv_suggested": "Suggested durable memory", "rv_scope": "Scope",
        "rv_evidence": "Evidence", "rv_summary": "Summary",
        "rv_project": "Project", "rv_category": "Category", "rv_risk": "Risk",
        "rv_source": "Source", "rv_created": "Created", "rv_weight": "Weight",
        "rv_confirm": "Confirm", "rv_cancel": "Cancel",
        "rv_rejected": "This proposal was rejected.",
        "rv_approved_synced": "This proposal was approved and synced.",
        "rv_superseded": "This proposal was superseded by a newer version.",
        "rv_all": "All", "rv_pending": "Pending", "rv_approved": "Approved", "rv_synced": "Synced",
        "rv_approve_db": "Save to memory", "rv_approve_export": "Approve & sync",
        "rv_promote_export": "Promote to sync", "rv_reject": "Reject this proposal",
        "kn_title": "Knowledge Tree", "kn_search": "Search knowledge…", "kn_add": "+ Add Knowledge",
        "kn_export": "⬇ Export MD", "kn_retrospect": "🔄 Retrospect",
        "kn_empty_trash": "🗑 Empty Trash", "kn_no_nodes": "No knowledge nodes match the current filters.",
        "kn_nodes": "nodes", "kn_all_cat": "All Categories", "kn_all_dom": "All Domains",
        "kn_stage_lifecycle": "Stage Lifecycle",
        "kn_draft_desc": "Raw knowledge. Unprocessed observations or manual entries. Auto-promotes to Refined after 3 conflict-free days.",
        "kn_refined_desc": "Agent-curated. De-duplicated & structured, but not yet fact-checked. Auto-promotes to Canonized after 7 conflict-free days.",
        "kn_verified_desc": "Source/user-confirmed facts. Reached via manual Promote. Can proceed to Canonize.",
        "kn_canonized_desc": "Core knowledge. High confidence, exported to KNOWLEDGE.md.",
        "kn_deprecated_desc": "Trash bin. Outdated, incorrect, or superseded knowledge. Click \"Empty Trash\" to permanently delete.",
        "kn_confidence_formula": "Confidence = category_base + source_bonus + evidence×0.05(cap 0.2) − corrections×0.1 + retrieval_bonus + time_bonus − age_penalty<br>Clamped [0.0, 1.0], Retrospect auto-recomputes.",
        "kn_close": "Close", "kn_cancel": "Cancel", "kn_submit": "Submit",
        "kn_content_label": "Content *", "kn_content_ph": "Enter knowledge content…",
        "kn_source_label": "Source", "kn_source_ph": "e.g. conversation, manual, observation",
        "kn_category_label": "Category", "kn_domain_label": "Domain",
        "kd_summary": "Summary", "kd_confidence": "Confidence", "kd_content": "Content",
        "kd_evidence": "Evidence", "kd_provenance": "Provenance",
        "kd_relationships": "Relationships", "kd_thought_chain": "Thought Chain Timeline",
        "kd_no_relationships": "No relationships",
        "kd_no_relationships_hint": "Connections to parent, child, or contradictory nodes will appear here.",
        "kd_no_evidence": "No evidence recorded",
        "kd_no_evidence_hint": "Supporting evidence will appear here when linked.",
        "kd_no_thought": "No thought chain entries",
        "kd_no_thought_hint": "Reasoning steps and decisions will be recorded here as this knowledge evolves.",
        "kd_parent": "Parent", "kd_child": "Child", "kd_supersedes": "Supersedes",
        "kd_superseded_by": "Superseded by", "kd_contradicts": "Contradicts",
        "kd_merged_from": "Merged From", "kd_contradicts_list": "Contradicts", "kd_verified_by": "Verified By",
        "kd_none_yet": "None yet",
        "kd_edit": "✏️ Edit", "kd_promote": "⬆ Promote to", "kd_deprecate": "🗑 Deprecate",
        "kd_delete_perm": "🗑 Delete Permanently", "kd_merge_into": "🔗 Merge into",
        "kd_no_actions": "Node is {stage} — no actions available.",
        "kd_back": "← Knowledge Tree",
        "kd_node_id": "Node ID", "kd_category": "Category", "kd_domain": "Domain",
        "kd_stage": "Stage", "kd_operation": "Operation", "kd_source_label": "Source",
        "kd_created": "Created", "kd_refined": "Refined", "kd_verified": "Verified",
        "kd_deprecated": "Deprecated", "kd_retrievals": "Retrievals", "kd_last_used": "Last Used",
        "kd_corrections": "Corrections", "kd_save": "Save", "kd_cancel": "Cancel",
        "kd_edit_title": "✏️ Edit Node",
        "kd_decision": "Decision", "kd_tl_confidence": "Confidence",
        "gl_title": "Sci-Fig Gallery",
        "gl_subtitle": "Scientific figure template library — view, approve, and contribute",
        "gl_search": "Search charts…", "gl_showing": "Showing", "gl_of": "of",
        "gl_submit": "+ Submit", "gl_image_url": "Image URL",
        "gl_image_url_ph": "https://...", "gl_or_upload": "Or Upload",
        "gl_notes": "Notes", "gl_notes_ph": "Figure type, paper source, what you like…",
        "gl_submit_btn": "Submit", "gl_interactive": "Interactive Chart",
        "gl_planned": "Planned",
        "gl_suggest": "✎ Suggest", "gl_suggest_ph": "Enter your suggestion…",
        "gl_approve_btn": "✓ Approve",
        "kd_evidence": "EVIDENCE", "kd_provenance": "PROVENANCE",
        "kd_relationships": "RELATIONSHIPS", "kd_thought": "THOUGHT CHAIN TIMELINE",
        "kd_no_evidence": "No evidence recorded",
        "kd_no_evidence_hint": "Supporting evidence will appear here when linked.",
        "kd_no_rel": "No relationships",
        "kd_no_rel_hint": "Connections to parent, child, or contradictory nodes will appear here.",
        "kd_no_thought": "No thought chain entries",
        "kd_no_thought_hint": "Reasoning steps and decisions will be recorded here as this knowledge evolves.",
        "kd_none_yet": "None yet",
        "kh_actions": "Action", "kh_approve": "Approve", "kh_reject": "Reject",
        "login_title": "Sign In", "login_subtitle": "Knowledge Management System", "login_user": "Username", "login_pass": "Password", "login_btn": "Sign In",
        "toast_added": "Added", "toast_export_done": "Export complete", "toast_retrospect_done": "Retrospect complete",
        "toast_deleted": "Deleted {count} nodes", "toast_done": "Done", "toast_node_updated": "Node updated",
        "toast_error": "Error", "toast_network_error": "Network error", "toast_copy_ok": "Copied", "toast_copy_fail": "Copy failed",
        "toast_no_interactive": "No interactive version available", "toast_approved": "Approved", "toast_rejected": "Rejected",
        "toast_suggestion_saved": "Suggestion saved", "toast_suggestion_noted": "Suggestion noted",
        "toast_enter_suggestion": "Enter a suggestion first", "toast_enter_palette_name": "Please enter a palette name",
        "toast_min_colors": "Enter at least 3 valid hex colors", "toast_palette_submitted": "Palette submitted! Thank you.",
        "toast_figure_submitted": "Figure submitted for analysis", "toast_upload_ok": "Template uploaded",
        "toast_upload_fail": "Upload failed", "toast_enter_url_or_file": "Provide an image URL or upload a file",
        "confirm_empty_trash": "Empty the recycle bin? This cannot be undone.",
        "confirm_delete_node": "Permanently delete this node?",
    },
}

def _pt(key: str, lang: str = "zh") -> str:
    """Python-side i18n lookup — returns zh text by default."""
    d = _I18N_DICT.get(lang, _I18N_DICT["zh"])
    return d.get(key, key)

# Input shape → Chinese tags (v3 has no tags; derive from input_shape)
_SHAPE_TAGS = {
    "point_table": ["散点", "差异表达"],
    "ordered_position_table": ["散点", "GWAS/QTL"],
    "matrix": ["热图", "聚类"],
    "pairwise_matrix": ["热图", "相关性"],
    "grouped_values": ["分布", "箱线"],
    "grouped_summary": ["柱状图", "分组比较"],
    "estimate_interval": ["临床", "森林图"],
    "ranked_term_table": ["散点", "富集"],
    "bipartite_links": ["散点", "富集"],
    "set_membership": ["集合图", "交集"],
    "embedding_table": ["散点", "降维"],
    "edge_table": ["网络/关系图", "互作"],
    "flow_table": ["网络/关系图", "冲积"],
    "classifier_curve": ["线图/曲线", "检验"],
    "time_to_event": ["线图/曲线", "生存"],
    "sparse_event_matrix": ["热图", "突变"],
    "positioned_events": ["散点", "位点标注"],
    "composition_table": ["面积图", "组成"],
    "ordered_composition_table": ["面积图", "组成"],
    "numeric_vector": ["分布", "直方图"],
    "embedding_with_loadings": ["散点", "降维", "载荷"],
    "aligned_event_matrix": ["热图", "神经信号", "事件对齐"],
    "time_aligned_events": ["线图/曲线", "神经信号", "事件对齐"],
}

# Chart id → Chinese description (v3 has no description; provide from title)
_ID_DESC = {
    "volcano": "展示基因差异表达的fold change与显著性，标注关键基因",
    "manhattan": "GWAS/QTL全局显著性概览，突出峰值位点",
    "heatmap_clustered": "行列双向聚类的热图，展示表达模式",
    "correlation_heatmap": "相关性矩阵热图，展示变量间关联强度",
    "box_violin": "展示组间数值分布差异",
    "raincloud": "云雨图：密度+箱线+散点，全面展示分布",
    "ridgeline": "山峦图：多组分布对比，适合时间序列或分组比较",
    "grouped_bar": "分组柱状图：多组定量比较",
    "enrichment_bubble": "展示GO/KEGG富集分析结果",
    "enrichment_circos": "圈图展示富集分析结果与基因关联",
    "forest_plot": "森林图：估计值与置信区间的可视化比较",
    "lollipop": "棒棒糖图：基因/位点标注的排名展示",
    "pca_plot": "PCA降维散点图：样本分组与聚类",
    "umap_plot": "UMAP降维散点图：细胞/样本嵌入可视化",
    "roc_curve": "ROC曲线：分类器性能评估",
    "km_survival": "Kaplan-Meier生存曲线",
    "sankey": "桑基图：流量/分类转化可视化",
    "network_graph": "网络图：节点与边的互作关系可视化",
    "upset_plot": "UpSet图：集合交集的定量可视化",
    "oncoplot": "Oncoplot：突变矩阵热图",
    "scatter": "散点图：两变量关联与分组对比，支持回归线",
    "stacked_area": "堆叠面积图：组成比例随时间/阶段的变化",
    "pca_biplot": "PCA双标图：散点+载荷箭头，展示特征对分组的贡献",
    "fiber_photometry": "光纤光度计热图：多trial z-score比较vehicle与drug",
    "syllable_frequency": "音节/行为频率比较：分组点图+SEM误差棒",
    "peri_event_raster": "事件对齐栅格图：per-trial轨迹+均值+热图",
}


def _normalize_catalog(raw: dict) -> dict:
    """Normalize v3 catalog format (templates/id/demo_png) to v2 (charts/name/demo).

    The gallery UI reads ``charts[].name``, ``charts[].demo``, ``charts[].tags``,
    and ``charts[].description``.  The new v3 catalog uses ``templates[].id``,
    ``templates[].demo_png``, ``templates[].input_shape``, etc.  Tags and
    descriptions are derived from input_shape and id when absent.
    """
    if "charts" in raw:
        return raw
    charts = []
    for tpl in raw.get("templates", []):
        _id = tpl.get("id", "")
        _shape = tpl.get("input_shape", "")
        charts.append({
            "name": _id,
            "title": tpl.get("title", ""),
            "description": tpl.get("description", _ID_DESC.get(_id, "")),
            "tier": tpl.get("tier", "P2"),
            "status": tpl.get("status", "planned"),
            "data_type": _shape,
            "required_fields": tpl.get("required_fields", []),
            "optional_fields": tpl.get("optional_fields", []),
            "visual_encodings": tpl.get("visual_encodings", {}),
            "reusable_for": tpl.get("reusable_for", []),
            "tags": tpl.get("tags", _SHAPE_TAGS.get(_shape, [])),
            "template": tpl.get("template", ""),
            "demo": tpl.get("demo_png", tpl.get("demo", "")),
        })
    return {"charts": charts}

# ---------------------------------------------------------------------------
# Shared CSS – shadcn-inspired OKLCH design system
# ---------------------------------------------------------------------------

_DARK_CSS = """\
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  /* 3-layer depth: bg → surface → card */
  --bg:oklch(.13 .01 270);
  --surface:oklch(.16 .01 270);
  --card:oklch(.20 .02 275);
  --card-hover:oklch(.25 .025 275);
  /* Borders */
  --border:oklch(1 0 0 / 10%);
  --border-hover:oklch(1 0 0 / 18%);
  --border-focus:#a78bfa;
  /* Text */
  --ink:#e2e4ed;
  --ink-muted:#8b90a5;
  --ink-dim:#5c6078;
  /* Semantic colors */
  --primary:#a78bfa;--primary-muted:rgba(167,139,250,.12);
  --success:#34d399;--success-muted:rgba(52,211,153,.12);
  --warning:#fbbf24;--warning-muted:rgba(251,191,36,.12);
  --danger:#f87171;--danger-muted:rgba(248,113,113,.12);
  --info:#67e8f9;--info-muted:rgba(103,232,249,.12);
  /* Radius scale */
  --r-sm:6px;--r-md:10px;--r-lg:14px;--r-xl:18px;--r-pill:999px;
  /* Shadows */
  --shadow-xs:0 1px 2px rgba(0,0,0,.2);
  --shadow-sm:0 2px 4px rgba(0,0,0,.25);
  --shadow-md:0 4px 12px rgba(0,0,0,.3);
  --shadow-lg:0 8px 24px rgba(0,0,0,.4);
  --shadow-xl:0 12px 40px rgba(0,0,0,.5);
  /* Spacing */
  --sp-xs:4px;--sp-sm:8px;--sp-md:16px;--sp-lg:24px;--sp-xl:32px;
  /* Font */
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  --font-mono:"JetBrains Mono","Fira Code","SF Mono",monospace;
  /* Transition */
  --ease-out:cubic-bezier(.16,1,.3,1);
  --duration:150ms;
  /* Sidebar */
  --sidebar-w:224px;
  --sidebar-w-collapsed:48px;
  --sidebar-bg:oklch(.14 .01 270);
  --sidebar-fg:var(--ink);
  --sidebar-muted:var(--ink-muted);
  --sidebar-primary:var(--primary);
  --sidebar-accent:oklch(.18 .02 275);
  --sidebar-border:var(--border);
  /* Header */
  --header-h:56px;
}
html[data-theme="light"]{
  --bg:oklch(.97 .005 270);
  --surface:oklch(.94 .005 270);
  --card:oklch(1 .003 275);
  --card-hover:oklch(.98 .006 275);
  --border:oklch(0 0 0 / 12%);
  --border-hover:oklch(0 0 0 / 20%);
  --border-focus:#7c3aed;
  --ink:#1a1a2e;
  --ink-muted:#5c6078;
  --ink-dim:#8b90a5;
  --sidebar-bg:oklch(.96 .005 270);
  --sidebar-accent:oklch(.93 .01 275);
}
html{font-family:var(--font);background:var(--surface);color:var(--ink);line-height:1.6;-webkit-text-size-adjust:100%;font-synthesis-weight:none;text-rendering:optimizeLegibility}
body{min-height:100vh;display:flex;min-height:100dvh}
a{color:var(--primary);text-decoration:none;transition:color var(--duration)}
a:hover{color:var(--ink)}
::selection{background:var(--primary);color:var(--bg)}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--surface)}
::-webkit-scrollbar-thumb{background:var(--card);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--ink-muted)}

/* ---- Animations ---- */
@keyframes fadeIn{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:scale(1)}}
@keyframes slideInRight{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
@keyframes slideUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
@keyframes pageEnter{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes staggerFade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes sidebarSlideIn{from{transform:translateX(-100%)}to{transform:translateX(0)}}
@keyframes dotPulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.6);opacity:.4}}
@keyframes toastSlideUp{from{opacity:0;transform:translateX(-50%) translateY(20px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
body{animation:pageEnter .35s var(--ease-out)}
/* Sidebar nav micro-interaction */
.sidebar-nav-item:hover{background:var(--sidebar-accent);color:var(--sidebar-fg);transform:translateX(2px)}
.sidebar-nav-item:active{transform:translateX(0) scale(.98)}
/* Button micro-interactions */
.pf-btn:active,.settings-btn:active{transform:translateY(0) scale(.97)}
.svc-card:active{transform:translateY(0) scale(.995)}
.dash-quick-tile:active{transform:scale(.97);box-shadow:none}
/* Health dot animation */
.svc-health-dot.checking{animation:pulse 1.5s infinite}
.svc-health-dot.alive{animation:dotPulse 2s ease-out 1}
/* Toast animation */
.pf-toast{animation:toastSlideUp .3s var(--ease-out)}
.tabs{animation:staggerFade .3s var(--ease-out) .05s both}
.search-bar{animation:staggerFade .3s var(--ease-out) .1s both}
.card-grid{animation:staggerFade .3s var(--ease-out) .1s both}
.dash-grid{animation:staggerFade .3s var(--ease-out) .08s both}
.card{animation:staggerFade .25s var(--ease-out) both}
.card:nth-child(1){animation-delay:.08s}.card:nth-child(2){animation-delay:.12s}.card:nth-child(3){animation-delay:.16s}.card:nth-child(4){animation-delay:.2s}.card:nth-child(5){animation-delay:.24s}.card:nth-child(6){animation-delay:.28s}
.section{animation:staggerFade .3s var(--ease-out) both}
.section:nth-child(2){animation-delay:.06s}.section:nth-child(3){animation-delay:.12s}.section:nth-child(4){animation-delay:.18s}.section:nth-child(5){animation-delay:.24s}
.dash-card{animation:staggerFade .25s var(--ease-out) both}
.dash-card:nth-child(1){animation-delay:.06s}.dash-card:nth-child(2){animation-delay:.1s}.dash-card:nth-child(3){animation-delay:.14s}.dash-card:nth-child(4){animation-delay:.18s}.dash-card:nth-child(5){animation-delay:.22s}.dash-card:nth-child(6){animation-delay:.26s}
.kn-domain-group{animation:staggerFade .25s var(--ease-out) both}
.action-bar{animation:slideUp .3s var(--ease-out) .15s both}

/* ---- Sidebar ---- */
.sidebar{
  position:fixed;top:0;left:0;bottom:0;
  width:var(--sidebar-w);
  background:var(--sidebar-bg);
  border-right:1px solid var(--sidebar-border);
  display:flex;flex-direction:column;
  z-index:60;
  transition:width .25s var(--ease-out),transform .25s var(--ease-out);
  overflow:hidden;
}
.sidebar.collapsed{width:var(--sidebar-w-collapsed)}
/* Brand header inside sidebar */
.sidebar-brand{
  display:flex;align-items:center;gap:var(--sp-sm);
  height:var(--header-h);padding:0 var(--sp-md);
  border-bottom:1px solid var(--sidebar-border);
  flex-shrink:0;white-space:nowrap;overflow:hidden;
}
.sidebar-brand .brand-logo{
  width:28px;height:28px;border-radius:var(--r-sm);
  background:linear-gradient(135deg,var(--primary),var(--info));
  display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:.8rem;color:var(--bg);flex-shrink:0;
}
.sidebar-brand .brand-name{
  font-size:1.05rem;font-weight:700;color:var(--sidebar-fg);
  transition:opacity .2s;letter-spacing:-.01em;
}
.sidebar.collapsed .brand-name{opacity:0;width:0;overflow:hidden}
/* Sidebar toggle button */
.sidebar-toggle{
  background:none;border:none;color:var(--ink-muted);
  cursor:pointer;padding:6px;border-radius:var(--r-sm);
  display:flex;align-items:center;justify-content:center;
  transition:color var(--duration),background var(--duration),transform .25s var(--ease-out);
  flex-shrink:0;
}
.sidebar-toggle:hover{color:var(--ink);background:var(--sidebar-accent)}
.sidebar-toggle svg{width:20px;height:20px}
.sidebar.collapsed .sidebar-toggle{
  position:absolute;left:50%;top:50%;transform:translate(-50%,-50%) rotate(180deg);
  padding:4px;margin:0;z-index:1;
}
.sidebar.collapsed .sidebar-brand{position:relative}
.sidebar.collapsed .brand-logo{opacity:.2;pointer-events:none}
/* Nav groups */
.sidebar-nav{flex:1;overflow-y:auto;overflow-x:hidden;padding:var(--sp-sm) 0}
.sidebar-nav-group{margin-bottom:var(--sp-sm)}
.sidebar-nav-label{
  padding:var(--sp-xs) var(--sp-md);font-size:.65rem;font-weight:600;
  text-transform:uppercase;letter-spacing:.08em;color:var(--ink-dim);
  white-space:nowrap;overflow:hidden;transition:opacity .2s;
}
.sidebar.collapsed .sidebar-nav-label{opacity:0;height:0;padding:0;margin:0;overflow:hidden}
.sidebar-nav-item{
  display:flex;align-items:center;gap:var(--sp-sm);
  padding:8px var(--sp-md);margin:1px var(--sp-xs);
  border-radius:var(--r-sm);color:var(--sidebar-muted);
  text-decoration:none;font-size:.84rem;font-weight:500;
  transition:all var(--duration) var(--ease-out);
  white-space:nowrap;overflow:hidden;min-height:36px;
  position:relative;
}
.sidebar-nav-item svg{width:18px;height:18px;flex-shrink:0}
.sidebar-nav-item span{transition:opacity .2s;overflow:hidden;text-overflow:ellipsis}
.sidebar.collapsed .sidebar-nav-item span{opacity:0;width:0}
.sidebar.collapsed .sidebar-nav-item{justify-content:center;padding:8px 0;margin:1px var(--sp-xs)}
.sidebar-nav-item.active{
  background:var(--primary-muted);color:var(--primary);
  font-weight:600;
}
.sidebar-nav-item.active::before{
  content:'';position:absolute;left:0;top:6px;bottom:6px;
  width:3px;border-radius:0 3px 3px 0;background:var(--primary);
}
/* User block at bottom */
.sidebar-user{
  border-top:1px solid var(--sidebar-border);
  padding:var(--sp-sm) var(--sp-md);display:flex;align-items:center;
  gap:var(--sp-sm);flex-shrink:0;overflow:hidden;
}
.sidebar-user-avatar{
  width:32px;height:32px;border-radius:50%;
  background:var(--sidebar-accent);display:flex;align-items:center;
  justify-content:center;flex-shrink:0;overflow:hidden;
}
.sidebar-user-avatar svg{width:16px;height:16px;color:var(--ink-muted)}
.sidebar-user-avatar img{width:100%;height:100%;object-fit:cover}
.sidebar-user-name{
  font-size:.82rem;font-weight:500;color:var(--sidebar-fg);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  transition:opacity .2s;
}
.sidebar.collapsed .sidebar-user-name{opacity:0;width:0}
.sidebar-user-link{display:flex;align-items:center;gap:10px;padding:var(--sp-sm) var(--sp-md);color:var(--ink);text-decoration:none;border-radius:var(--r-md);margin:var(--sp-xs) var(--sp-sm);transition:background .2s}
.sidebar-user-link:hover{background:var(--sidebar-accent)}

/* ---- Top Header Bar ---- */
.top-header{
  position:fixed;top:0;right:0;height:var(--header-h);
  display:flex;align-items:center;gap:var(--sp-sm);
  padding:0 var(--sp-lg);z-index:55;
  background:oklch(.14 .01 270 / 80%);
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border-bottom:1px solid var(--border);
  transition:left .25s var(--ease-out);
  left:var(--sidebar-w);
}
.top-header .header-left{display:flex;align-items:center;gap:var(--sp-sm);flex:1}
.top-header .header-right{display:flex;align-items:center;gap:var(--sp-sm)}
/* Mobile hamburger button - visible only on mobile */
.header-mobile-toggle{
  display:none;background:none;border:none;color:var(--ink-muted);
  cursor:pointer;padding:6px;border-radius:var(--r-sm);
  align-items:center;justify-content:center;
  transition:color var(--duration),background var(--duration);
}
.header-mobile-toggle:hover{color:var(--ink);background:var(--card-hover)}
.header-mobile-toggle svg{width:22px;height:22px}
/* Header action buttons */
.header-btn{
  background:none;border:1px solid var(--border);color:var(--ink-muted);
  cursor:pointer;padding:6px;border-radius:var(--r-sm);
  display:flex;align-items:center;justify-content:center;
  transition:all var(--duration);min-width:32px;min-height:32px;
}
.header-btn:hover{color:var(--ink);border-color:var(--border-hover);background:var(--card-hover)}
.header-btn svg{width:18px;height:18px}

/* ---- Main content area ---- */
.main-wrap{
  flex:1;display:flex;flex-direction:column;
  margin-left:var(--sidebar-w);
  padding-top:var(--header-h);
  min-height:100vh;min-height:100dvh;
  transition:margin-left .25s var(--ease-out);
  overflow-x:hidden;
}
.sidebar.collapsed ~ .main-wrap{margin-left:var(--sidebar-w-collapsed)}
.sidebar.collapsed ~ .top-header{left:var(--sidebar-w-collapsed)}
.sidebar-toggle svg{transition:transform .25s var(--ease-out)}

/* ---- Mobile sidebar overlay ---- */
.sidebar-overlay{
  display:none;position:fixed;inset:0;
  background:rgba(0,0,0,.55);backdrop-filter:blur(4px);
  z-index:59;
}

/* ---- Responsive: mobile ---- */
@media(max-width:767px){
  .sidebar{transform:translateX(-100%);width:var(--sidebar-w)}
  .sidebar.collapsed{width:var(--sidebar-w)}
  .sidebar.mobile-open{transform:translateX(0)}
  .sidebar-overlay.open{display:block}
  .main-wrap{margin-left:0 !important}
  .top-header{left:0}
  .header-mobile-toggle{display:flex}
  .sidebar.collapsed ~ .main-wrap{margin-left:0}
}
/* Desktop: hide mobile toggle */
@media(min-width:768px){
  .header-mobile-toggle{display:none !important}
}

/* ---- Filter tabs ---- */
.tabs{display:flex;gap:6px;padding:var(--sp-md) var(--sp-md) var(--sp-sm);overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tabs a,.tabs button{
  display:inline-flex;align-items:center;gap:6px;
  padding:8px 16px;border:1px solid var(--border);border-radius:var(--r-pill);
  background:transparent;color:var(--ink-muted);font-size:.84rem;font-weight:500;cursor:pointer;
  min-height:44px;white-space:nowrap;transition:all var(--duration)
}
.tabs a.active,.tabs button.active{background:var(--primary-muted);color:var(--ink);border-color:var(--primary);box-shadow:0 0 0 1px var(--primary)}
.tabs a:hover,.tabs button:hover{background:var(--border-hover);color:var(--ink)}
.tab-count{font-size:.72rem;background:var(--border-hover);border-radius:var(--r-pill);padding:1px 7px;color:var(--ink-dim);font-weight:600;margin-left:2px}

/* ---- Card grid ---- */
.card-grid{display:grid;grid-template-columns:1fr;gap:var(--sp-md);padding:0 var(--sp-md) var(--sp-md)}
@media(min-width:720px){.card-grid{grid-template-columns:repeat(auto-fill,minmax(380px,1fr))}}

.card{display:block;background:var(--card);border-radius:var(--r-lg);padding:var(--sp-md);border:1px solid var(--border);text-decoration:none;color:var(--ink);min-height:44px;transition:all var(--duration) var(--ease-out);box-shadow:var(--shadow-xs)}
.card:hover{border-color:var(--primary);background:var(--card-hover);text-decoration:none;transform:translateY(-2px) scale(1.02);box-shadow:var(--shadow-lg),0 0 0 1px var(--primary)}
.card-top{display:flex;align-items:center;gap:var(--sp-sm);flex-wrap:wrap;margin-bottom:var(--sp-sm)}
.card-preview{font-size:.9rem;color:var(--ink);overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;max-width:100%;line-height:1.5}
.card-meta{display:flex;gap:var(--sp-sm);margin-top:var(--sp-sm);font-size:.78rem;color:var(--ink-muted)}

/* ---- Badges ---- */
.badge{display:inline-flex;align-items:center;height:22px;padding:2px 10px;border-radius:var(--r-pill);font-size:.7rem;font-weight:600;letter-spacing:.02em;white-space:nowrap;transition:all var(--duration);box-shadow:0 1px 2px rgba(0,0,0,.15)}
.badge-pending{background:var(--warning-muted);color:var(--warning)}
.badge-approved_db_only{background:var(--success-muted);color:var(--success)}
.badge-approved_for_export{background:rgba(52,211,153,.22);color:var(--success)}
.badge-rejected{background:var(--danger-muted);color:var(--danger)}
.badge-superseded{background:var(--border-hover);color:var(--ink-dim)}
.badge-rule{background:var(--primary-muted);color:var(--primary)}
.badge-pattern{background:var(--info-muted);color:var(--info)}
.badge-insight{background:rgba(251,146,60,.12);color:#fb923c}
.badge-warning{background:rgba(251,113,133,.12);color:#fb7185}
.badge-risk-high{background:var(--danger-muted);color:var(--danger)}
.badge-risk-medium{background:var(--warning-muted);color:var(--warning)}
.badge-risk-low{background:var(--success-muted);color:var(--success)}

/* ---- Detail page ---- */
.detail-header{padding:var(--sp-md);display:flex;align-items:center;gap:var(--sp-sm);flex-wrap:wrap}
.back-link{display:inline-flex;align-items:center;gap:4px;color:var(--ink-muted);font-size:.88rem;min-height:44px;border-radius:var(--r-sm);transition:color var(--duration)}
.back-link:hover{color:var(--primary)}
.detail-title{font-size:1.1rem;font-weight:700;word-break:break-all;color:var(--ink)}
.detail-body{padding:0 var(--sp-md) var(--sp-md)}
.section{margin-bottom:var(--sp-lg);background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-md);position:relative;padding-left:calc(var(--sp-md) + 4px);transition:border-color var(--duration)}
.section::before{content:'';position:absolute;left:0;top:var(--r-lg);bottom:var(--r-lg);width:4px;border-radius:0 4px 4px 0;background:var(--primary);opacity:.6;transition:opacity var(--duration)}
.section:hover{border-color:var(--border-hover)}
.section:hover::before{opacity:1}
.section h3{color:var(--primary);font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:var(--sp-sm);font-weight:600}
.section p{color:var(--ink);font-size:.9rem;white-space:pre-wrap;word-break:break-word;line-height:1.6}
.meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-sm) var(--sp-md);padding:var(--sp-md);font-size:.84rem}
.meta-grid .label{color:var(--ink-muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em}
.meta-grid .value{color:var(--ink);font-weight:500}

/* ---- Action buttons ---- */
.action-bar{
  position:fixed;bottom:0;left:0;right:0;
  display:flex;gap:var(--sp-sm);padding:var(--sp-sm) var(--sp-md);
  background:var(--surface);border-top:1px solid var(--border);
  backdrop-filter:blur(8px);z-index:100
}
body:has(.action-bar){padding-bottom:76px}
.action-bar .btn{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;padding:12px var(--sp-sm);border:none;border-radius:var(--r-md);font-size:.9rem;font-weight:600;cursor:pointer;min-height:48px;transition:all var(--duration) var(--ease-out);position:relative;overflow:hidden}
.action-bar .btn:active{transform:translateY(1px)}
.btn-approve{background:var(--success-muted);color:var(--success);transition:all var(--duration) var(--ease-out)}
.btn-approve:hover{background:rgba(52,211,153,.25);box-shadow:var(--shadow-sm),0 0 12px rgba(52,211,153,.15)}
.btn-export{background:var(--primary-muted);color:var(--primary);transition:all var(--duration) var(--ease-out)}
.btn-export:hover{background:rgba(167,139,250,.25);box-shadow:var(--shadow-sm),0 0 12px rgba(167,139,250,.15)}
.btn-reject{background:var(--danger-muted);color:var(--danger);transition:all var(--duration) var(--ease-out)}
.btn-reject:hover{background:rgba(248,113,113,.25);box-shadow:var(--shadow-sm),0 0 12px rgba(248,113,113,.15)}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none}
.btn:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(167,139,250,.3)}
kbd{font-family:var(--font-mono);font-size:.68rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-sm);padding:1px 5px;margin-left:4px;color:var(--ink-dim);font-weight:500}

/* ---- Dashboard ---- */
.dash-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;padding:0 var(--sp-md) var(--sp-md)}
@media(min-width:720px){.dash-grid{grid-template-columns:repeat(4,1fr)}}
.dash-card{background:var(--card);border-radius:var(--r-lg);padding:var(--sp-lg) var(--sp-md);border:1px solid var(--border);text-align:center;box-shadow:var(--shadow-xs);transition:all var(--duration) var(--ease-out);position:relative;overflow:hidden}
.dash-card::after{content:'';position:absolute;bottom:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--primary),var(--info));opacity:0;transition:opacity var(--duration)}
.dash-card:hover{border-color:var(--border-focus);box-shadow:var(--shadow-md);transform:translateY(-2px)}
.dash-card:hover::after{opacity:1}
.dash-card .num{font-size:2rem;font-weight:700;line-height:1}
.dash-card .label{font-size:.75rem;color:var(--ink-muted);margin-top:4px;text-transform:uppercase;letter-spacing:.06em}
.dash-section{padding:0 var(--sp-md) var(--sp-md)}
.dash-section h3{color:var(--primary);font-size:.88rem;margin-bottom:var(--sp-sm);font-weight:600}
.dash-table{width:100%;border-collapse:collapse;font-size:.84rem}
.dash-table th,.dash-table td{padding:var(--sp-sm) 12px;text-align:left;border-bottom:1px solid var(--border)}
.dash-table th{color:var(--ink-muted);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em}
.dash-table td{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:120px}
.dash-details{padding:0 var(--sp-md) var(--sp-sm)}
.dash-details-header{display:flex;align-items:center;gap:var(--sp-sm);padding:var(--sp-sm) var(--sp-md);cursor:pointer;font-size:.92rem;font-weight:600;color:var(--ink);user-select:none;border-bottom:1px solid var(--border);background:var(--card);border-radius:var(--r-lg);margin:var(--sp-sm) 0;transition:background var(--duration)}
.dash-details-header:hover{background:var(--card-hover)}
.dash-details-count{font-size:.72rem;background:var(--border-hover);border-radius:var(--r-pill);padding:2px 8px;color:var(--ink-dim);margin-left:auto}
.dash-details[open] .dash-details-header{border-radius:var(--r-lg) var(--r-lg) 0 0}

/* ---- Exports list ---- */
.export-list{padding:0 var(--sp-md) var(--sp-md)}
.export-item{display:flex;align-items:center;justify-content:space-between;padding:var(--sp-sm) var(--sp-md);background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);margin-bottom:var(--sp-sm);min-height:44px;gap:var(--sp-sm);text-decoration:none;color:var(--ink);transition:all var(--duration);box-shadow:var(--shadow-xs)}
.export-item:hover{border-color:var(--border-focus);background:var(--card-hover);text-decoration:none;box-shadow:var(--shadow-sm)}
.export-item .file-name{font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.export-item .file-meta{font-size:.78rem;color:var(--ink-muted);display:flex;gap:var(--sp-sm);flex-shrink:0}
.export-item .download-icon{color:var(--primary);font-size:1.2rem;flex-shrink:0}

/* ---- State dot ---- */
.state-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;vertical-align:middle}
.state-dot-pending{background:var(--warning)}
.state-dot-approved_db_only{background:var(--success)}
.state-dot-approved_for_export{background:var(--success)}
.state-dot-rejected{background:var(--danger)}
.state-dot-superseded{background:var(--ink-dim)}

/* ---- Empty state ---- */
.empty{padding:var(--sp-xl) var(--sp-md);text-align:center;color:var(--ink-dim);font-size:.95rem}

/* ---- Quota board ---- */
.quota-summary{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;padding:0 var(--sp-md) var(--sp-sm)}
@media(min-width:720px){.quota-summary{grid-template-columns:repeat(4,1fr)}}
.quota-summary .qs-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:14px 10px;text-align:center;box-shadow:var(--shadow-xs)}
.quota-summary .qs-num{font-size:1.6rem;font-weight:700;line-height:1}
.quota-summary .qs-label{font-size:.72rem;color:var(--ink-muted);margin-top:2px;text-transform:uppercase;letter-spacing:.04em}
.quota-board{padding:0 var(--sp-md) var(--sp-md)}
.quota-col-header{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:var(--sp-sm);padding:var(--sp-sm) 12px;font-size:.72rem;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border)}
.quota-row{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:var(--sp-sm);align-items:center;padding:10px 12px;border-bottom:1px solid var(--border);font-size:.84rem;transition:background var(--duration)}
.quota-row:hover{background:var(--card)}
.quota-row .qr-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500}
.quota-row .qr-bar{height:6px;border-radius:3px;background:var(--border-hover);overflow:hidden;min-width:60px}
.quota-row .qr-bar-fill{height:100%;border-radius:3px;transition:width .3s}
.quota-row .qr-status{font-size:.78rem;font-weight:600}
.quota-col-section{padding:var(--sp-md) var(--sp-md) var(--sp-xs);font-size:.84rem;font-weight:600;color:var(--primary);display:flex;align-items:center;gap:6px}
.quota-col-section .qcs-count{font-size:.72rem;color:var(--ink-dim);font-weight:400}
.refresh-info{padding:var(--sp-xs) var(--sp-md) var(--sp-sm);font-size:.72rem;color:var(--ink-dim);margin-left:auto;white-space:nowrap}

/* ---- Confirm modal ---- */
.confirm-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.55);backdrop-filter:blur(8px);z-index:200;justify-content:center;align-items:center}
.confirm-overlay[style*="flex"]{animation:fadeIn var(--duration) var(--ease-out)}
.confirm-modal{background:var(--card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-lg);max-width:380px;width:90%;text-align:center;box-shadow:var(--shadow-xl);animation:fadeIn var(--duration) var(--ease-out);transform:scale(1)}
.confirm-modal h3{font-size:1.05rem;margin:0 0 var(--sp-sm);color:var(--ink);font-weight:600}
.confirm-modal .confirm-actions{display:flex;gap:var(--sp-sm);justify-content:center;margin-top:var(--sp-md)}
.confirm-modal .confirm-actions button{padding:10px 24px;border:none;border-radius:var(--r-md);font-size:.88rem;font-weight:600;cursor:pointer;min-height:44px;transition:all var(--duration) var(--ease-out)}
.confirm-modal .btn-yes{background:var(--primary);color:var(--bg)}
.confirm-modal .btn-yes:hover{opacity:.85;box-shadow:var(--shadow-sm)}
.confirm-modal .btn-yes:active{transform:translateY(1px)}
.confirm-modal .btn-no{background:var(--border-hover);color:var(--ink)}
.confirm-modal .btn-no:hover{background:var(--card-hover)}

/* ---- Toast (global) ---- */
.toast{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:var(--r-lg);font-size:.88rem;font-weight:600;z-index:300;opacity:0;transform:translateX(20px);transition:all .2s var(--ease-out);pointer-events:none;box-shadow:var(--shadow-lg)}
.toast.show{opacity:1;transform:translateX(0)}
.toast-approve{background:var(--success);color:var(--bg)}
.toast-reject{background:var(--danger);color:#fff}
.toast-export{background:var(--primary);color:var(--bg)}

/* ---- Search bar ---- */
.search-bar{display:flex;gap:var(--sp-sm);padding:var(--sp-sm) var(--sp-md) 0}
.search-bar input{flex:1;padding:10px 14px;border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface);color:var(--ink);font-size:.88rem;outline:none;transition:border-color var(--duration),box-shadow var(--duration);min-height:44px}
.search-bar input:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(167,139,250,.25),0 0 0 1px var(--primary)}
.search-bar input::placeholder{color:var(--ink-dim)}

/* ---- Dashboard Hero ---- */
.dash-hero{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--sp-md);padding:var(--sp-lg) var(--sp-lg) 0}
@media(max-width:720px){.dash-hero{grid-template-columns:repeat(2,1fr);gap:var(--sp-sm);padding:var(--sp-md) var(--sp-md) 0}.dash-health-strip{padding:0 var(--sp-md);gap:var(--sp-sm)}.dash-health-item{padding:4px 10px;font-size:.72rem}}
.dash-metric{background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-lg) var(--sp-md);display:flex;flex-direction:column;gap:2px;transition:border-color var(--duration)}
.dash-metric:hover{border-color:var(--border-hover)}
.dash-metric .dash-num{font-size:1.75rem;font-weight:700;line-height:1.1;letter-spacing:-.02em}
.dash-metric .dash-label{font-size:.72rem;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.06em;font-weight:500}
.dash-metric .dash-sub{font-size:.72rem;color:var(--ink-dim);margin-top:2px}
.dash-metricAccent{border-left:3px solid var(--primary)}
.dash-metricSuccess .dash-num{color:var(--success)}
.dash-metricPrimary .dash-num{color:var(--primary)}
.dash-metricWarning .dash-num{color:var(--warning)}
.dash-metricDanger .dash-num{color:var(--danger)}
.dash-charts-row{display:grid;grid-template-columns:1.2fr 1fr;gap:var(--sp-md);margin-top:var(--sp-md)}
@media(max-width:720px){.dash-charts-row{grid-template-columns:1fr}}
/* ---- API section (full-width) ---- */
.dash-api-section{margin:var(--sp-lg) var(--sp-lg) 0;padding:var(--sp-lg);background:var(--card);border:1px solid var(--border);border-radius:var(--r-xl);animation:staggerFade .3s var(--ease-out) .04s both}
@media(max-width:720px){.dash-api-section{margin:var(--sp-md);padding:var(--sp-md)}}
.dash-api-header{display:flex;align-items:center;justify-content:space-between;gap:var(--sp-sm);margin-bottom:var(--sp-md)}
.dash-api-header h2{font-size:.95rem;font-weight:600;color:var(--ink);margin:0;display:flex;align-items:center;gap:var(--sp-sm)}
.dash-api-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--sp-md)}
@media(max-width:720px){.dash-api-grid{grid-template-columns:repeat(2,1fr)}}
.dash-api-card{text-align:center;padding:var(--sp-sm) var(--sp-md)}
.dash-api-card .dash-num{font-size:1.35rem}
.dash-api-card .dash-label{font-size:.7rem}
.dash-trend-wrap{margin-top:var(--sp-md)}
.dash-trend-label{font-size:.7rem;color:var(--ink-dim);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em}
.dash-trend-chart-box{height:140px;position:relative}
/* ---- Service health strip ---- */
.dash-health-strip{display:flex;gap:var(--sp-md);padding:0 var(--sp-lg);flex-wrap:wrap}
.dash-health-item{display:flex;align-items:center;gap:6px;padding:6px 14px;background:var(--card);border:1px solid var(--border);border-radius:var(--r-pill);font-size:.78rem;color:var(--ink-muted);transition:border-color var(--duration),background var(--duration)}
.dash-health-item:hover{border-color:var(--border-hover);background:var(--card-hover)}
.dash-health-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dash-health-dot.alive{background:var(--success);box-shadow:0 0 6px rgba(52,211,153,.5)}
.dash-health-dot.dead{background:var(--danger);box-shadow:0 0 6px rgba(248,113,113,.4)}
.dash-health-dot.checking{background:var(--warning);animation:pulse 1.5s infinite}
.dash-health-name{font-weight:500;color:var(--ink)}
.dash-health-lat{font-family:var(--font-mono);font-size:.68rem;color:var(--ink-dim)}
/* ---- Uptime Kuma embed ---- */
.dash-uptime-section{margin:var(--sp-md) var(--sp-lg) 0;animation:staggerFade .3s var(--ease-out) .12s both}
.dash-uptime-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;transition:border-color var(--duration)}
.dash-uptime-card:hover{border-color:var(--border-hover)}
.dash-uptime-header{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border)}
.dash-uptime-header h3{margin:0;font-size:.88rem;font-weight:600;color:var(--ink)}
.dash-uptime-grid{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-sm);padding:var(--sp-md)}
.dash-uptime-item{display:flex;align-items:center;gap:var(--sp-md);padding:var(--sp-md) var(--sp-lg);background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);text-decoration:none;color:var(--ink);transition:border-color .2s,background .2s}
.dash-uptime-item:hover{border-color:var(--primary);background:rgba(167,139,250,.06)}
.dash-uptime-icon{font-size:1.5rem;flex-shrink:0}
.dash-uptime-info{flex:1;min-width:0}
.dash-uptime-name{font-size:.84rem;font-weight:600;color:var(--ink)}
.dash-uptime-desc{font-size:.72rem;color:var(--ink-muted);margin-top:2px}
.dash-uptime-arrow{font-size:1.1rem;color:var(--ink-muted);flex-shrink:0;transition:transform .2s}
.dash-uptime-item:hover .dash-uptime-arrow{transform:translateX(3px);color:var(--primary)}
.dash-uptime-link{font-size:.76rem;color:var(--primary);text-decoration:none;font-weight:500;transition:color .2s}
.dash-uptime-link:hover{color:var(--primary-hover,var(--primary))}
.dash-uptime-note{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);padding:10px 14px;margin-top:var(--sp-sm);font-size:.78rem;color:var(--ink-muted);display:flex;align-items:center;gap:var(--sp-sm)}
.dash-uptime-note .note-icon{font-size:1rem;flex-shrink:0}
.dash-uptime-note strong{color:var(--ink);font-weight:600}
@media(max-width:720px){.dash-uptime-section{margin:var(--sp-md)}.dash-uptime-grid{grid-template-columns:1fr;padding:var(--sp-sm)}}
/* ---- Resource gauges ---- */
.dash-resource-section{margin:var(--sp-md) var(--sp-lg) 0;display:grid;grid-template-columns:repeat(4,1fr);gap:var(--sp-md);animation:staggerFade .3s var(--ease-out) .06s both}
@media(max-width:720px){.dash-resource-section{grid-template-columns:repeat(2,1fr);margin:var(--sp-md);gap:var(--sp-sm)}}
.dash-res-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-md);display:flex;flex-direction:column;gap:4px;transition:border-color var(--duration)}
.dash-res-card:hover{border-color:var(--border-hover)}
.dash-res-label{font-size:.7rem;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.06em;font-weight:500}
.dash-res-value{font-size:1.3rem;font-weight:700;line-height:1.1}
.dash-res-bar{height:4px;border-radius:2px;background:var(--surface);overflow:hidden;margin-top:2px}
.dash-res-fill{height:100%;border-radius:2px;transition:width .6s var(--ease-out)}
.dash-res-sub{font-size:.68rem;color:var(--ink-dim);font-family:var(--font-mono)}
/* ---- Account health donut ---- */
.dash-donut-wrap{display:flex;align-items:center;gap:var(--sp-lg);margin-top:var(--sp-md)}
.dash-donut-canvas-wrap{width:100px;height:100px;flex-shrink:0}
.dash-donut-legend{display:flex;flex-direction:column;gap:6px}
.dash-donut-legend-item{display:flex;align-items:center;gap:8px;font-size:.82rem}
.dash-donut-legend-dot{width:10px;height:10px;border-radius:3px;flex-shrink:0}
.dash-donut-legend-value{font-weight:600;font-family:var(--font-mono)}
/* ---- VPS section ---- */
.sec-header{display:flex;align-items:center;gap:var(--sp-sm);padding:var(--sp-md) var(--sp-lg) var(--sp-sm);border-bottom:1px solid var(--border)}
.sec-header h1{font-size:1rem;margin:0;font-weight:600;color:var(--ink);flex:1;letter-spacing:-.01em}
.sec-refresh{font-size:.72rem;color:var(--success);display:inline-flex;align-items:center;gap:4px;font-weight:500}
.sec-refresh::before{content:'';display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--success);box-shadow:0 0 6px rgba(52,211,153,.5);animation:pulse 2s infinite}
.sec-pause-btn{background:none;border:1px solid var(--border);border-radius:var(--r-sm);color:var(--ink-muted);padding:4px 10px;cursor:pointer;font-size:.78rem;transition:all var(--duration);min-height:28px;min-width:28px;display:inline-flex;align-items:center;justify-content:center}
.sec-pause-btn:hover{border-color:var(--primary);color:var(--primary)}
.sec-kanban{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-lg);padding:var(--sp-md) var(--sp-lg) var(--sp-lg)}
@media(max-width:720px){.sec-kanban{grid-template-columns:1fr;padding:var(--sp-md)}}
.sec-col{min-width:0;animation:staggerFade .35s var(--ease-out) both}
.sec-col:nth-child(2){animation-delay:.08s}
.sec-col-header{display:flex;align-items:center;gap:var(--sp-sm);padding:var(--sp-sm) 0;margin-bottom:var(--sp-sm);border-bottom:1px solid var(--border)}
.sec-col-header h3{font-size:.85rem;margin:0;color:var(--ink-muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em;flex:1}
.sec-section{margin-bottom:var(--sp-md);animation:staggerFade .3s var(--ease-out) both}
.sec-section:nth-child(2){animation-delay:.04s}
.sec-section:nth-child(3){animation-delay:.08s}
.sec-section:nth-child(4){animation-delay:.12s}
.sec-section-title{font-size:.7rem;font-weight:600;color:var(--ink-dim);text-transform:uppercase;letter-spacing:.08em;padding:0 0 var(--sp-xs);margin:0 0 var(--sp-xs)}
.sec-card{background:var(--card);border-radius:var(--r-lg);padding:14px 16px;margin-bottom:var(--sp-sm);border:1px solid var(--border);transition:border-color var(--duration)}
.sec-card:hover{border-color:var(--border-hover)}
.sec-overview{border-left:3px solid var(--primary)}
.sec-empty{color:var(--ink-dim);font-size:.82rem;font-style:italic;padding:var(--sp-sm) 0;display:block;text-align:center}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;flex-shrink:0}
.dot-green{background:var(--success)}
.dot-red{background:var(--danger)}
.dot-amber{background:var(--warning)}
.sec-badge{font-size:.68rem;padding:2px 8px;border-radius:var(--r-pill);background:var(--card-hover);color:var(--ink-muted);margin-left:6px;font-weight:500;letter-spacing:.02em;white-space:nowrap}
.sec-badge-red{background:var(--danger-muted);color:var(--danger);font-weight:600}
.sec-badge-green{background:var(--success-muted);color:var(--success);font-weight:600}
.sec-stat-row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;font-size:.86rem;border-bottom:1px solid var(--border)}
.sec-stat-row:last-child{border-bottom:none}
.sec-stat-row .stat-label{color:var(--ink-muted);font-size:.82rem}
.sec-stat-row .stat-value{font-weight:600;color:var(--ink)}
.sec-bar-row{display:flex;align-items:center;gap:var(--sp-sm);padding:4px 0;font-size:.82rem}
.sec-ip{min-width:130px;color:var(--ink-dim);font-family:var(--font-mono);font-size:.76rem;overflow:hidden;text-overflow:ellipsis}
.sec-bar-bg{flex:1;height:6px;background:var(--border-hover);border-radius:3px;overflow:hidden}
.sec-bar-fill{height:100%;border-radius:3px;transition:width .6s var(--ease-out);min-width:2px}
.sec-cnt{min-width:40px;text-align:right;color:var(--ink-dim);font-size:.76rem;font-family:var(--font-mono)}
.sec-ufw-row{display:flex;align-items:center;gap:var(--sp-sm);padding:6px 2px;font-size:.82rem;border-bottom:1px solid var(--border);transition:background var(--duration)}
.sec-ufw-row:hover{background:var(--card-hover);border-radius:var(--r-sm)}
.sec-ufw-row:last-child{border-bottom:none}
.sec-ufw-action{min-width:48px;font-weight:700;font-size:.74rem;letter-spacing:.02em;border-radius:var(--r-pill);padding:1px 6px;text-align:center;display:inline-block}
.sec-ufw-action.allow{background:var(--success-muted);color:var(--success)}
.sec-ufw-action.deny{background:var(--danger-muted);color:var(--danger)}
.sec-ufw-action.other{background:var(--card-hover);color:var(--ink-dim)}
.sec-ufw-to{min-width:90px;font-family:var(--font-mono);font-size:.76rem;color:var(--ink);font-weight:500}
.sec-ufw-comment{color:var(--ink-dim);font-size:.74rem;font-style:italic}
.sec-inbound-card{background:var(--card);border-radius:var(--r-lg);padding:14px 16px;margin-bottom:var(--sp-sm);border:1px solid var(--border);transition:border-color var(--duration)}
.sec-inbound-card:hover{border-color:var(--border-hover)}
.sec-inbound-header{display:flex;align-items:center;gap:var(--sp-sm);flex-wrap:wrap}
.sec-inbound-name{font-weight:600;font-size:.88rem;color:var(--ink)}
.sec-inbound-meta{font-size:.74rem;color:var(--ink-dim);font-family:var(--font-mono)}
.sec-inbound-traffic{font-size:.76rem;margin-left:auto;font-weight:500;color:var(--ink-muted);font-family:var(--font-mono)}
.sec-inbound-clients{margin-top:var(--sp-sm);padding-left:16px;border-left:2px solid var(--border)}
.sec-client-row{display:flex;align-items:center;gap:var(--sp-sm);padding:5px 0;font-size:.82rem;border-bottom:1px solid var(--border)}
.sec-client-row:last-child{border-bottom:none}
.sec-client-name{min-width:120px;color:var(--ink);font-weight:500}
.sec-client-traffic{color:var(--ink-dim);font-size:.76rem;font-family:var(--font-mono)}
.sec-sysctl-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:var(--sp-xs)}
@media(max-width:480px){.sec-sysctl-grid{grid-template-columns:1fr 1fr}}
.sec-sysctl-item{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:var(--surface);border-radius:var(--r-md);font-size:.82rem;border:1px solid transparent;transition:border-color var(--duration)}
.sec-sysctl-item:hover{border-color:var(--border)}
.sec-sysctl-label{color:var(--ink-muted);font-size:.76rem}
.sec-sysctl-value{font-weight:600;font-size:.9rem}
.sec-api-status{display:flex;align-items:center;gap:var(--sp-xs);font-size:.78rem;margin-top:var(--sp-sm)}
.sec-api-status .dot{margin-right:0}
"""

# ---------------------------------------------------------------------------
# Shared page shell
# ---------------------------------------------------------------------------

def _page(title: str, body: str, *, extra_js: str = "", nav_active: str = "home", show_nav: bool = True) -> str:
    """Return a full HTML document with sidebar + top header layout."""
    if show_nav:
        nav_html = _nav(active=nav_active)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='18' fill='%237c3aed'/><text x='50' y='72' font-size='60' font-family='sans-serif' font-weight='bold' fill='white' text-anchor='middle'>B</text></svg>">
<title>{_html.escape(title)}</title>
<style>{_DARK_CSS}</style>
<script>var _I18N={_json.dumps(_I18N_DICT, ensure_ascii=False)};function _t(key){{var lang=localStorage.getItem('hermes_lang')||'zh';var dict=_I18N[lang]||_I18N.zh;return dict[key]||key;}}function applyI18n(lang){{if(!lang)lang=localStorage.getItem('hermes_lang')||'zh';var dict=_I18N[lang]||_I18N.zh;document.querySelectorAll('[data-i18n]').forEach(function(el){{var key=el.getAttribute('data-i18n');if(dict[key])el.textContent=dict[key];}});document.querySelectorAll('[data-i18n-ph]').forEach(function(el){{var key=el.getAttribute('data-i18n-ph');if(dict[key])el.placeholder=dict[key];}});var g=document.getElementById('dash-greeting-text');if(g){{var h=new Date().getHours();var name=localStorage.getItem('hermes_display_name')||dict.pf_explorer;g.textContent=(h<12?dict.greeting_morning:h<18?dict.greeting_afternoon:dict.greeting_evening)+dict.time_comma+name;}}}}function switchLang(lang){{localStorage.setItem('hermes_lang',lang);var sel=document.getElementById('lang-select');if(sel)sel.value=lang;applyI18n(lang);}}</script>
<script>(function(){{var t=localStorage.getItem('hermes_theme');if(t==='light')document.documentElement.setAttribute('data-theme','light');}})();document.addEventListener('DOMContentLoaded',function(){{var n=localStorage.getItem('hermes_display_name');if(n){{var su=document.getElementById('sidebar-username');if(su)su.textContent=n;}}var a=localStorage.getItem('hermes_avatar_url');if(a){{var sa=document.getElementById('sidebar-avatar');if(sa)sa.innerHTML='<img src=\"'+a+'\" style=\"width:100%;height:100%;object-fit:cover;border-radius:50%\" onerror=\"this.outerHTML=this.dataset.fallback\" data-fallback=\"👤\">';}}applyI18n();}});</script>
</head>
<body>
{nav_html}
<div class="main-wrap">
{body}
</div>
{extra_js if extra_js.strip().startswith('<script') or not extra_js.strip() else f'<script>{extra_js}</script>'}
</body>
</html>"""
    else:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='18' fill='%237c3aed'/><text x='50' y='72' font-size='60' font-family='sans-serif' font-weight='bold' fill='white' text-anchor='middle'>B</text></svg>">
<title>{_html.escape(title)}</title>
<style>{_DARK_CSS}</style>
<script>var _I18N={_json.dumps(_I18N_DICT, ensure_ascii=False)};function _t(key){{var lang=localStorage.getItem('hermes_lang')||'zh';var dict=_I18N[lang]||_I18N.zh;return dict[key]||key;}}function applyI18n(lang){{if(!lang)lang=localStorage.getItem('hermes_lang')||'zh';var dict=_I18N[lang]||_I18N.zh;document.querySelectorAll('[data-i18n]').forEach(function(el){{var key=el.getAttribute('data-i18n');if(dict[key])el.textContent=dict[key];}});document.querySelectorAll('[data-i18n-ph]').forEach(function(el){{var key=el.getAttribute('data-i18n-ph');if(dict[key])el.placeholder=dict[key];}});var g=document.getElementById('dash-greeting-text');if(g){{var h=new Date().getHours();var name=localStorage.getItem('hermes_display_name')||dict.pf_explorer;g.textContent=(h<12?dict.greeting_morning:h<18?dict.greeting_afternoon:dict.greeting_evening)+dict.time_comma+name;}}}}function switchLang(lang){{localStorage.setItem('hermes_lang',lang);var sel=document.getElementById('lang-select');if(sel)sel.value=lang;applyI18n(lang);}}</script>
<script>(function(){{var t=localStorage.getItem('hermes_theme');if(t==='light')document.documentElement.setAttribute('data-theme','light');}})();document.addEventListener('DOMContentLoaded',function(){{var n=localStorage.getItem('hermes_display_name');if(n){{var su=document.getElementById('sidebar-username');if(su)su.textContent=n;}}var a=localStorage.getItem('hermes_avatar_url');if(a){{var sa=document.getElementById('sidebar-avatar');if(sa)sa.innerHTML='<img src=\"'+a+'\" style=\"width:100%;height:100%;object-fit:cover;border-radius:50%\" onerror=\"this.outerHTML=this.dataset.fallback\" data-fallback=\"👤\">';}};applyI18n();}});</script>
</head>
<body>
{body}
{extra_js if extra_js.strip().startswith('<script') or not extra_js.strip() else f'<script>{extra_js}</script>'}
</body>
</html>"""


# SVG icons for nav items
_ICON_QUEUE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>'
_ICON_STATUS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>'
_ICON_EXPORT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
_ICON_SECURITY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
_ICON_LOGOUT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>'

_ICON_QUOTA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>'
_ICON_GROK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/></svg>'
_ICON_GALLERY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>'
_ICON_SHIELD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
_ICON_KNOWLEDGE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'


_ICON_SETTINGS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'

_ICON_HOME = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>'

_ICON_SERVICES = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="9" height="9" rx="2"/><rect x="13" y="2" width="9" height="9" rx="2"/><rect x="2" y="13" width="9" height="9" rx="2"/><rect x="13" y="13" width="9" height="9" rx="2"/></svg>'

_ICON_USER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'

_ICON_EXTERNAL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>'

def _nav(*, active: str = "home") -> str:
    """Sidebar navigation + top header bar with toggle."""
    # Icon for sidebar collapse/expand (hamburger / menu)
    icon_menu = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>'
    icon_chevron = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>'

    nav_items = [
        ("home", "首页", "/", _ICON_HOME),
        ("knowledge", "知识", "/knowledge", _ICON_KNOWLEDGE),
        ("gallery", "绘图", "/gallery", _ICON_GALLERY),
        ("services", "服务", "/services", _ICON_SERVICES),
    ]
    nav_items_html = []
    for key, label, href, icon in nav_items:
        cls = "sidebar-nav-item active" if key == active else "sidebar-nav-item"
        nav_items_html.append(
            f'<a href="{href}" class="{cls}">{icon}<span data-i18n="nav_{key}">{_html.escape(label)}</span></a>'
        )

    profile_cls = "sidebar-nav-item active" if active == "profile" else "sidebar-nav-item"

    sidebar = f"""<aside class="sidebar" id="brainSidebar">
  <div class="sidebar-brand">
    <div class="brand-logo">B</div>
    <span class="brand-name">Brain</span>
    <button type="button" class="sidebar-toggle" id="sidebarToggle" title="Toggle sidebar" onclick="var s=document.getElementById('brainSidebar');s.classList.toggle('collapsed');localStorage.setItem('hermes_sidebar_collapsed',s.classList.contains('collapsed')?'1':'0')">
      {icon_chevron}
    </button>
  </div>
  <nav class="sidebar-nav">
    <div class="sidebar-nav-group">
      <div class="sidebar-nav-label" data-i18n="nav_label">导航</div>
      {''.join(nav_items_html)}
      <a href="/profile" class="{profile_cls}">{_ICON_USER}<span data-i18n="nav_profile">我的</span></a>
    </div>
  </nav>
  <a href="/profile" class="sidebar-user-link">
    <div class="sidebar-user-avatar" id="sidebar-avatar">{_ICON_USER}</div>
    <span class="sidebar-user-name" id="sidebar-username" data-i18n="nav_user">用户</span>
  </a>
</aside>"""

    top_header = f"""<header class="top-header" id="topHeader">
  <div class="header-left">
    <button type="button" class="header-mobile-toggle" id="mobileMenuToggle" title="Menu">
      {icon_menu}
    </button>
  </div>
  <div class="header-right">
    <a href="/profile" class="header-btn" title="Profile">{_ICON_USER}</a>
  </div>
</header>"""

    overlay = '<div class="sidebar-overlay" id="sidebarOverlay"></div>'

    toggle_js = """(function(){
  var sb=document.getElementById('brainSidebar');
  var mobile=document.getElementById('mobileMenuToggle');
  var overlay=document.getElementById('sidebarOverlay');
  if(!sb)return;
  /* Restore sidebar collapsed state from localStorage */
  if(localStorage.getItem('hermes_sidebar_collapsed')==='1'&&window.innerWidth>=768){
    sb.classList.add('collapsed');
  }
  /* Toggle function used by both onclick and addEventListener */
  window._toggleSidebar=function(){
    if(window.innerWidth<768){
      sb.classList.remove('mobile-open');
      if(overlay)overlay.classList.remove('open');
    } else {
      sb.classList.toggle('collapsed');
      localStorage.setItem('hermes_sidebar_collapsed',sb.classList.contains('collapsed')?'1':'0');
    }
  };
  var toggle=document.getElementById('sidebarToggle');
  if(toggle){
    /* Remove onclick to prevent double-fire; use addEventListener only */
    toggle.removeAttribute('onclick');
    toggle.addEventListener('click',window._toggleSidebar);
  }
  if(mobile){
    mobile.addEventListener('click',function(){
      sb.classList.toggle('mobile-open');
      if(overlay)overlay.classList.toggle('open');
    });
  }
  if(overlay){
    overlay.addEventListener('click',function(){
      sb.classList.remove('mobile-open');
      overlay.classList.remove('open');
    });
  }
  /* Restore user prefs from localStorage */
  var _dn=localStorage.getItem('hermes_display_name');
  if(_dn){var _su=document.getElementById('sidebar-username');if(_su)_su.textContent=_dn;}
  var _au=localStorage.getItem('hermes_avatar_url');
  if(_au){var _sa=document.getElementById('sidebar-avatar');if(_sa)_sa.innerHTML='<img src="'+_au+'" style="width:100%;height:100%;object-fit:cover;border-radius:50%" onerror="this.outerHTML=this.dataset.fallback" data-fallback="👤">';}
})();"""

    return f"""{sidebar}
{top_header}
{overlay}
<script>{toggle_js}</script>"""


# ---------------------------------------------------------------------------
# Category / risk badge helpers
# ---------------------------------------------------------------------------

_CATEGORY_BADGE_MAP = {
    "rule": "badge-rule",
    "pattern": "badge-pattern",
    "insight": "badge-insight",
    "warning": "badge-warning",
}


def _category_badge(category: str) -> str:
    cls = _CATEGORY_BADGE_MAP.get(category, "badge-rule")
    return f'<span class="badge {cls}">{_html.escape(category)}</span>'


_RISK_BADGE_MAP = {
    "high": "badge-risk-high",
    "medium": "badge-risk-medium",
    "low": "badge-risk-low",
}


def _risk_badge(risk_level: str) -> str:
    cls = _RISK_BADGE_MAP.get(risk_level, "badge-risk-medium")
    return f'<span class="badge {cls}">{_html.escape(risk_level)}</span>'


_STATE_BADGE_MAP = {
    "pending": "badge-pending",
    "approved_db_only": "badge-approved_db_only",
    "approved_for_export": "badge-approved_for_export",
    "rejected": "badge-rejected",
    "superseded": "badge-superseded",
}

# Human-readable labels for states (Chinese-friendly)
_STATE_LABEL = {
    "pending": "Pending",
    "approved_db_only": "Approved",
    "approved_for_export": "Approved + Synced",
    "rejected": "Rejected",
    "superseded": "Outdated",
}

_STATE_DOT_MAP = {
    "pending": "state-dot-pending",
    "approved_db_only": "state-dot-approved_db_only",
    "approved_for_export": "state-dot-approved_for_export",
    "rejected": "state-dot-rejected",
    "superseded": "state-dot-superseded",
}


def _state_badge(state: str) -> str:
    cls = _STATE_BADGE_MAP.get(state, "badge-pending")
    dot = _STATE_DOT_MAP.get(state, "state-dot-pending")
    label = _STATE_LABEL.get(state, state.replace("_", " ").title())
    return f'<span class="badge {cls}"><span class="state-dot {dot}"></span>{_html.escape(label)}</span>'


# ---------------------------------------------------------------------------
# Review Queue page
# ---------------------------------------------------------------------------

def review_queue_page(
    *,
    proposals: list[dict],
    counts: dict[str, int],
    active_state: str = "pending",
) -> str:
    """Render the review queue with filter tabs and proposal cards."""
    total = sum(counts.values())
    tabs = [
        ("all", _pt("rv_all"), total),
        ("pending", _pt("rv_pending"), counts.get("pending", 0)),
        ("approved_db_only", _pt("rv_approved"), counts.get("approved_db_only", 0)),
        ("approved_for_export", _pt("rv_synced"), counts.get("approved_for_export", 0)),
    ]
    tab_html = ""
    for key, label, count in tabs:
        active_cls = " active" if (key == active_state) or (key == "all" and active_state == "all") else ""
        href = f"/review?state={key}" if key != "pending" else "/review"
        if key == "all":
            href = "/review?state=all"
        tab_html += (
            f'<a href="{href}" class="{active_cls.lstrip()}">'
            f'{_html.escape(label)} <span class="tab-count">{count}</span></a>'
        )

    cards = ""
    for p in proposals:
        pid = str(p.get("proposal_id", ""))
        cat = str(p.get("category", ""))
        risk = str(p.get("risk_level", ""))
        memory = str(p.get("suggested_memory", ""))
        project = str(p.get("project_key", ""))
        state = str(p.get("state", "pending"))
        # Truncate preview to 120 chars
        preview = memory[:120] + ("..." if len(memory) > 120 else "")
        cards += f"""<a href="/review/{_html.escape(pid)}" class="card">
  <div class="card-top">{_category_badge(cat)} {_state_badge(state)}</div>
  <div class="card-preview">{_html.escape(preview)}</div>
  <div class="card-meta">
    <span>{_html.escape(project)}</span>
    {_risk_badge(risk)}
  </div>
</a>"""

    if not proposals:
        cards = f'<div class="empty">{_pt("rv_no_proposals")}</div>'

    # The heading must contain "Pending proposals" for the test
    heading = _pt("stat_pending") if active_state == "pending" else f"{active_state.replace('_', ' ').title()} proposals"

    body = f"""
<h1 style="padding:16px 16px 0;font-size:1.2rem">{_html.escape(heading)}</h1>
<div class="tabs">{tab_html}</div>
<div class="search-bar"><input type="text" id="search-input" data-i18n-ph="rv_search" placeholder="{_pt('rv_search')}" oninput="filterCards()"></div>
<div class="card-grid" id="card-grid">{cards}</div>
<script>
function filterCards(){{
  var q = document.getElementById('search-input').value.toLowerCase();
  var cards = document.querySelectorAll('#card-grid .card');
  cards.forEach(function(c){{
    c.style.display = c.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
"""
    return _page("Hermes Review Queue", body, nav_active="home")


# ---------------------------------------------------------------------------
# Review Detail page
# ---------------------------------------------------------------------------

_PROPOSAL_SECTIONS_KEYS = [
    ("rv_observation", "observation"),
    ("rv_why_matters", "why_it_matters"),
    ("rv_suggested", "suggested_memory"),
    ("rv_scope", "scope"),
    ("rv_evidence", "evidence"),
    ("rv_summary", "summary"),
]

# JavaScript for action buttons – uses fetch + confirm
_ACTION_JS = """\
function act(url, actionName) {
  var overlay = document.getElementById('confirm-overlay');
  var modal = document.getElementById('confirm-modal');
  var modalTitle = document.getElementById('confirm-title');
  var modalBtn = document.getElementById('confirm-action-btn');
  modalTitle.textContent = actionName + '?';
  modalBtn.onclick = function() {
    overlay.style.display = 'none';
    var btn = document.querySelector('.action-bar .btn:focus, .action-bar .btn:hover') || document.activeElement;
    if (btn) btn.disabled = true;
    fetch(url, {method:'POST',headers:{'Content-Type':'application/json'}})
      .then(function(r){ return r.json(); })
      .then(function(data){
        if (data.next_id) {
          window.location.href = '/review/' + data.next_id;
        } else {
          window.location.href = '/review';
        }
      })
      .catch(function(e){
        showToast(_t('toast_error') + ': ' + e.message, 'reject');
        if (btn) btn.disabled = false;
      });
  };
  overlay.style.display = 'flex';
  modalBtn.focus();
}
function hideConfirm() {
  document.getElementById('confirm-overlay').style.display = 'none';
}
function showToast(msg, type) {
  var t = document.createElement('div');
  t.className = 'toast toast-' + (type||'approve');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function(){ t.classList.add('show'); },10);
  setTimeout(function(){ t.classList.remove('show'); setTimeout(function(){ t.remove(); },300); },2500);
}
document.addEventListener('keydown', function(e){
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  var btns = document.querySelectorAll('.action-bar .btn');
  if (e.key === 'a' || e.key === 'A') { if(btns[0]) btns[0].click(); }
  else if (e.key === 's' || e.key === 'S') { if(btns[1]) btns[1].click(); }
  else if (e.key === 'r' || e.key === 'R') { if(btns[2]) btns[2].click(); }
  else if (e.key === 'p' || e.key === 'P') { if(btns[1] && btns[1].textContent.includes('Promote')) btns[1].click(); }
  else if (e.key === 'Escape') { hideConfirm(); }
});
"""


def review_detail_page(*, proposal: dict) -> str:
    """Render the full detail view for a single proposal with action buttons."""
    pid = str(proposal.get("proposal_id", ""))
    state = str(proposal.get("state", "pending"))
    project = str(proposal.get("project_key", ""))
    category = str(proposal.get("category", ""))
    risk = str(proposal.get("risk_level", ""))
    source_agent = str(proposal.get("source_agent", ""))
    created_at = str(proposal.get("created_at", ""))

    # Sections
    sections_html = ""
    for i18n_key, key in _PROPOSAL_SECTIONS_KEYS:
        val = str(proposal.get(key, ""))
        sections_html += f"""<div class="section">
  <h3 data-i18n="{_html.escape(i18n_key)}">{_pt(i18n_key)}</h3>
  <p>{_html.escape(val)}</p>
</div>"""

    # Determine which buttons are available
    is_pending = state == "pending"
    is_approved_db = state == "approved_db_only"
    is_rejected = state == "rejected"

    weight = str(proposal.get("weight", ""))
    weight_html = f'<span class="label" data-i18n="rv_weight">{_pt("rv_weight")}</span><span class="value">{_html.escape(weight)}</span>' if weight else ''

    # Action buttons
    btns = ""
    if is_pending or is_approved_db:
        btns += (
            f'<button class="btn btn-approve" onclick="act(\'/api/review/{_html.escape(pid)}/approve-db-only?state={_html.escape(state)}\',\'{_pt("rv_approve_db")}\')">'
            f'✓ {_pt("kh_approve")} <kbd>A</kbd></button>'
        )
        btns += (
            f'<button class="btn btn-export" onclick="act(\'/api/review/{_html.escape(pid)}/approve-for-export?state={_html.escape(state)}\',\'{_pt("rv_approve_export")}\')">'
            f'↗ {_pt("kh_approve")} & {_pt("rv_synced")} <kbd>S</kbd></button>'
        )
    if is_approved_db:
        btns += (
            f'<button class="btn btn-export" onclick="act(\'/api/review/{_html.escape(pid)}/promote-to-export?state={_html.escape(state)}\',\'{_pt("rv_promote_export")}\')">'
            '⬆ Promote <kbd>P</kbd></button>'
        )
    if is_pending or is_approved_db:
        btns += (
            f'<button class="btn btn-reject" onclick="act(\'/api/review/{_html.escape(pid)}/reject?state={_html.escape(state)}\',\'{_pt("rv_reject")}\')">'
            f'✕ {_pt("kh_reject")} <kbd>R</kbd></button>'
        )
    if is_rejected:
        btns = f'<div class="empty" style="flex:1" data-i18n="rv_rejected">{_pt("rv_rejected")}</div>'
    if state in ("approved_for_export",):
        btns = f'<div class="empty" style="flex:1" data-i18n="rv_approved_synced">{_pt("rv_approved_synced")}</div>'
    if state == "superseded":
        btns = f'<div class="empty" style="flex:1" data-i18n="rv_superseded">{_pt("rv_superseded")}</div>'

    # If no action buttons were set (e.g. rejected was not handled above)
    if not btns and is_rejected:
        btns = f'<div class="empty" style="flex:1" data-i18n="rv_rejected">{_pt("rv_rejected")}</div>'

    body = f"""
<div class="detail-header">
  <a href="/review" class="back-link" data-i18n="rv_review">{_pt("rv_review")}</a>
  <span class="detail-title">{_html.escape(pid[:12])}…</span>
  {_state_badge(state)}
</div>
<div class="meta-grid">
  <span class="label" data-i18n="rv_project">{_pt("rv_project")}</span><span class="value">{_html.escape(project)}</span>
  <span class="label" data-i18n="rv_category">{_pt("rv_category")}</span><span class="value">{_category_badge(category)}</span>
  <span class="label" data-i18n="rv_risk">{_pt("rv_risk")}</span><span class="value">{_risk_badge(risk)}</span>
  <span class="label" data-i18n="rv_source">{_pt("rv_source")}</span><span class="value">{_html.escape(source_agent)}</span>
  <span class="label" data-i18n="rv_created">{_pt("rv_created")}</span><span class="value">{_html.escape(created_at[:19])}</span>
  {weight_html}
</div>
<div class="detail-body">{sections_html}</div>
<div class="action-bar">{btns}</div>
<div class="confirm-overlay" id="confirm-overlay" onclick="if(event.target===this)hideConfirm()">
  <div class="confirm-modal" id="confirm-modal">
    <h3 id="confirm-title"></h3>
    <div class="confirm-actions">
      <button class="btn-yes" id="confirm-action-btn" data-i18n="rv_confirm">{_pt("rv_confirm")}</button>
      <button class="btn-no" onclick="hideConfirm()" data-i18n="rv_cancel">{_pt("rv_cancel")}</button>
    </div>
  </div>
</div>
"""
    return _page(f"Proposal {pid[:12]}", body, extra_js=_ACTION_JS, nav_active="home")


# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

def login_page(*, error: str = "") -> str:
    """Render a username/password login form that sets a session cookie."""
    error_html = f'<div class="login-error">{_html.escape(error)}</div>' if error else ""
    body = f"""<div class="login-wrapper">
<div class="login-card">
  <div class="login-brand">
    <div class="login-logo">🧠</div>
    <h1 class="login-title" data-i18n="login_title">Sign In</h1>
    <p class="login-subtitle" data-i18n="login_subtitle">Knowledge Management System</p>
  </div>
  {error_html}
  <form method="POST" action="/login" class="login-form">
    <label class="login-label" data-i18n="login_user">Username</label>
    <div class="login-input-wrap">
      <svg class="login-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      <input type="text" name="username" autocomplete="username" class="login-input" placeholder="Username" data-i18n-ph="login_user" autofocus>
    </div>
    <label class="login-label" data-i18n="login_pass">Password</label>
    <div class="login-input-wrap">
      <svg class="login-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      <input type="password" name="password" autocomplete="current-password" class="login-input" placeholder="Password" data-i18n-ph="login_pass">
    </div>
    <button type="submit" class="login-btn" data-i18n="login_btn">Sign In</button>
  </form>
  <p class="login-hint">
    API: <code>Authorization: Bearer &lt;token&gt;</code>
  </p>
</div>
</div>"""
    login_css = """
<style>
.login-wrapper{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:16px;background:radial-gradient(ellipse at 50% 0%,rgba(167,139,250,.08) 0%,transparent 60%)}
.login-card{background:var(--card);border-radius:var(--r-xl);padding:40px 32px;max-width:380px;width:100%;border:1px solid var(--border);box-shadow:var(--shadow-lg);animation:fadeIn .4s var(--ease-out)}
.login-brand{text-align:center;margin-bottom:28px}
.login-logo{font-size:2.4rem;margin-bottom:4px;animation:slideUp .4s var(--ease-out)}
.login-title{font-size:1.5rem;font-weight:700;margin:0;background:linear-gradient(135deg,var(--primary),var(--info));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.login-subtitle{font-size:.82rem;color:var(--ink-muted);margin-top:4px;letter-spacing:.02em}
.login-error{background:var(--danger-muted);color:var(--danger);padding:10px 14px;border-radius:var(--r-md);font-size:.88rem;text-align:center;margin-bottom:16px;border:1px solid var(--danger);animation:staggerFade .3s var(--ease-out)}
.login-form{display:flex;flex-direction:column;gap:4px}
.login-label{display:block;font-size:.82rem;color:var(--ink-muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:.06em;font-weight:500}
.login-input-wrap{position:relative;margin-bottom:14px}
.login-icon{position:absolute;left:12px;top:50%;transform:translateY(-50%);width:18px;height:18px;color:var(--ink-dim);pointer-events:none;transition:color var(--duration)}
.login-input{width:100%;padding:12px 12px 12px 40px;border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface);color:var(--ink);font-size:.95rem;min-height:48px;outline:none;transition:border-color var(--duration),box-shadow var(--duration)}
.login-input:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(167,139,250,.2)}
.login-input:focus+.login-icon,.login-input:focus~.login-icon{color:var(--primary)}
.login-input-wrap:focus-within .login-icon{color:var(--primary)}
.login-btn{width:100%;padding:14px;border:none;border-radius:var(--r-md);background:linear-gradient(135deg,var(--primary),#818cf8);color:#fff;font-size:1rem;font-weight:600;cursor:pointer;min-height:48px;transition:all var(--duration) var(--ease-out);margin-top:4px;position:relative;overflow:hidden}
.login-btn:hover{box-shadow:var(--shadow-md),0 0 20px rgba(167,139,250,.25);transform:translateY(-1px)}
.login-btn:active{transform:translateY(1px);box-shadow:var(--shadow-sm)}
.login-hint{text-align:center;margin-top:20px;font-size:.72rem;color:var(--ink-dim);line-height:1.5}
.login-hint code{background:var(--surface);padding:2px 8px;border-radius:var(--r-sm);border:1px solid var(--border);font-size:.72rem;font-family:var(--font-mono)}
</style>
"""
    return _page("Hermes Login", login_css + body, show_nav=False)


# ---------------------------------------------------------------------------
# Color Palettes Data & Builder (embedded in Gallery)
# ---------------------------------------------------------------------------

_PAL_QUAL = {
    "okabe_ito": ("Okabe-Ito", "Okabe & Ito (2008) — CVD gold standard", True,
        [("#E69F00","Orange"), ("#56B4E9","Sky Blue"), ("#009E73","Bluish Green"), ("#F0E442","Yellow"), ("#0072B2","Blue"), ("#D55E00","Vermillion"), ("#CC79A7","Red. Purple"), ("#000000","Black")]),
    "tol_bright": ("Paul Tol Bright", "Paul Tol (2021) — srON, 7 colors", True,
        [("#4477AA","Blue"), ("#EE6677","Red"), ("#228833","Green"), ("#CCBB44","Yellow"), ("#66CCEE","Cyan"), ("#AA3377","Purple"), ("#BBBBBB","Grey")]),
    "tol_vibrant": ("Paul Tol Vibrant", "Tol (2021) — TensorBoard-style", True,
        [("#0077BB","Blue"), ("#33BBEE","Cyan"), ("#009988","Teal"), ("#EE7733","Orange"), ("#CC3311","Red"), ("#EE3377","Magenta"), ("#BBBBBB","Grey")]),
    "tol_muted": ("Paul Tol Muted", "Tol (2021) — 9 colors + bad-data grey", True,
        [("#332288","Indigo"), ("#88CCEE","Cyan"), ("#44AA99","Teal"), ("#117733","Green"), ("#999933","Olive"), ("#DDCC77","Sand"), ("#CC6677","Rose"), ("#882255","Wine"), ("#AA4499","Purple")]),
    "npg": ("NPG (Nature Rev. Cancer)", "Nature Publishing Group, via ggsci", False,
        [("#E64B35","Red"), ("#4DBBD5","Cyan Blue"), ("#00A087","Green"), ("#3C5488","Navy"), ("#F39B7F","Salmon"), ("#8491B8","Slate"), ("#91D1C2","Mint"), ("#DC0000","Crimson"), ("#7E6148","Brown"), ("#B09C85","Tan")]),
    "nejm": ("NEJM", "New England J. Medicine, via ggsci", True,
        [("#BC3C29","Dark Red"), ("#0072B5","Blue"), ("#E18727","Orange"), ("#20854E","Green"), ("#7876B1","Purple"), ("#6F99AD","Steel"), ("#FFDC91","Gold"), ("#EE4C97","Pink")]),
    "lancet": ("Lancet", "The Lancet, via ggsci", True,
        [("#00468B","Blue"), ("#ED0000","Red"), ("#42B540","Green"), ("#0099B5","Teal"), ("#925E9F","Purple"), ("#FDAF91","Peach"), ("#AD002A","Dark Red"), ("#ADB6B6","Grey")]),
    "jama": ("JAMA", "J. American Medical Association", True,
        [("#374E55","Charcoal"), ("#DF8D5B","Orange"), ("#003B5C","Navy"), ("#B6370E","Rust"), ("#56B3E0","Sky"), ("#00A087","Teal")]),
    "jco": ("JCO", "J. Clinical Oncology, via ggsci", True,
        [("#0073A8","Blue"), ("#E08B28","Amber"), ("#A0244D","Magenta"), ("#56B3E0","Lt. Blue"), ("#3C5488","Navy"), ("#91D1C2","Mint"), ("#DC0000","Red"), ("#7E6148","Brown")]),
    "aaas": ("AAAS (Science)", "American Assoc. Advancement Science", False,
        [("#3B4BA0","Indigo"), ("#EB0E2F","Red"), ("#7B95D1","Periwinkle"), ("#EF7C5E","Salmon"), ("#68AABA","Teal"), ("#C598C5","Lavender")]),
}

_PAL_GENO = {
    "volcano": ("Volcano Plot", "DE up/down/NS + Okabe-Ito", True,
        [("#D55E00","Up-regulated"), ("#0072B2","Down-regulated"), ("#BBBBBB","Not significant"), ("#000000","Threshold")]),
    "apa_pattern": ("APA Usage Pattern", "Alt. polyadenylation convention", True,
        [("#E64B35","Proximal"), ("#4DBBD5","Distal"), ("#8491B8","No change")]),
    "survival": ("KM Survival Curves", "High-contrast risk groups", True,
        [("#D55E00","High risk"), ("#0072B2","Low risk"), ("#BBBBBB","Censored")]),
    "gwas": ("GWAS Manhattan", "Chromosome alternating standard", False,
        [("#3366CC","Even chr"), ("#CC3333","Odd chr"), ("#D55E00","Genome-wide"), ("#0072B2","Suggestive")]),
    "fluorophore": ("Fluorophore CVD-Safe", "Microscopy channels from Okabe-Ito", True,
        [("#0072B2","Ch1 Blue"), ("#E69F00","Ch2 Orange"), ("#D55E00","Ch3 Vermillion"), ("#CC79A7","Ch4 Magenta"), ("#F0E442","Ch5 Yellow")]),
    "dna_bases": ("DNA Bases CVD-Safe", "Sequence visualization", True,
        [("#009E73","A (Green)"), ("#0072B2","C (Blue)"), ("#E69F00","G (Orange)"), ("#D55E00","T (Vermillion)")]),
}

_PAL_CMAP = [
    ("viridis", "Viridis", "Blue→Green→Yellow, most versatile", "#440154,#31688e,#35b779,#fde725"),
    ("magma", "Magma", "Black→Purple→Orange→White", "#000004,#51127c,#f98e09,#fcfdbf"),
    ("inferno", "Inferno", "Black→Purple→Red→Yellow", "#000004,#56106e,#bb3754,#fcffa4"),
    ("plasma", "Plasma", "Purple→Pink→Orange→Yellow", "#0d0887,#7e03a8,#cc4778,#f0f921"),
    ("cividis", "Cividis", "Blue→Yellow, CVD-optimized", "#00224e,#6b8cc4,#feb9ff"),
    ("batlow", "Batlow (Crameri)", "Gold-blue, perceptually uniform", "#1d0c30,#5a235a,#a6606b,#f5b7b1,#faf7f7"),
    ("roma", "Roma (Crameri)", "Diverging: warm→white→cool", "#762a83,#c4a66c,#f5f0e5,#88c4ac,#1a6a54"),
    ("vik", "Vik (Crameri)", "Diverging: cool→white→warm", "#1a6a54,#88c4ac,#f5f0e5,#c4a66c,#762a83"),
    ("tol_sunset", "Tol Sunset", "Diverging: blue→yellow→red", "#364B9A,#6AA2AE,#E2E7B8,#F5A962,#A50026"),
    ("tol_burd", "Tol BuRd", "Diverging: blue→white→red", "#2166AC,#67A9CF,#F7F7F7,#EF8A62,#B2182B"),
    ("rdylbu", "RdYlBu", "Diverging: red→yellow→blue", "#A50026,#F46D43,#FFFFBF,#74ADD1,#313695"),
]


def _build_palettes_section() -> str:
    """Build the Color Palettes section HTML for embedding in Gallery."""
    # Qualitative palette cards
    _q = ""
    for _pid, (_name, _src, _cvd, _colors) in _PAL_QUAL.items():
        _cvd_tag = '<span class="cvd-yes">✓ CVD</span>' if _cvd else '<span class="cvd-no">✗ CVD</span>'
        _sw = "".join(f'<div class="pal-swatch" style="background:{c}" title="{l}: {c}" data-hex="{c}" onclick="event.stopPropagation();copyHex(this)"><span class="pal-hex">{c}</span></div>' for c, l in _colors)
        _q += f'<div class="palette-card" data-cvd="{str(_cvd).lower()}" data-pid="{_pid}" onclick="openPaletteDetail(this.dataset.pid)"><div class="pal-head"><span class="pal-name">{_name}</span>{_cvd_tag}</div><div class="pal-src">{_src}</div><div class="pal-swatches">{_sw}</div><div class="pal-footer"><code class="pal-copy" data-pid="{_pid}" onclick="event.stopPropagation();copyPalette(this)">{len(_colors)} colors — click to copy</code></div></div>\n'

    # Genomics palette cards
    _g = ""
    for _pid, (_name, _src, _cvd, _colors) in _PAL_GENO.items():
        _cvd_tag = '<span class="cvd-yes">✓ CVD</span>' if _cvd else '<span class="cvd-no">✗ CVD</span>'
        _sw = "".join(f'<div class="pal-swatch" style="background:{c}" title="{l}: {c}" data-hex="{c}" onclick="event.stopPropagation();copyHex(this)"><span class="pal-hex">{c}</span></div>' for c, l in _colors)
        _g += f'<div class="palette-card" data-cvd="{str(_cvd).lower()}" data-pid="{_pid}" onclick="openPaletteDetail(this.dataset.pid)"><div class="pal-head"><span class="pal-name">{_name}</span>{_cvd_tag}</div><div class="pal-src">{_src}</div><div class="pal-swatches">{_sw}</div><div class="pal-footer"><code class="pal-copy" data-pid="{_pid}" onclick="event.stopPropagation();copyPalette(this)">{len(_colors)} colors — click to copy</code></div></div>\n'

    # Sequential/diverging cmap table
    _t = ""
    for _cid, _label, _desc, _stops in _PAL_CMAP:
        _grad = f"background:linear-gradient(90deg,{_stops})"
        _t += f'<tr><td><code>{_cid}</code></td><td>{_label}</td><td>{_desc}</td><td><span class="cvd-yes" style="font-size:.6rem">✓</span></td><td><div class="cmap-bar" style="{_grad}"></div></td></tr>\n'

    # Build palette JS data for copy functionality
    _pal_data_parts = []
    for _pid, (_name, _src, _cvd, _colors) in _PAL_QUAL.items():
        _hex_list = "[" + ",".join(f'"{c}"' for c, l in _colors) + "]"
        _pal_data_parts.append(f'"{_pid}":{_hex_list}')
    for _pid, (_name, _src, _cvd, _colors) in _PAL_GENO.items():
        _hex_list = "[" + ",".join(f'"{c}"' for c, l in _colors) + "]"
        _pal_data_parts.append(f'"{_pid}":{_hex_list}')
    _pal_js = "{" + ",".join(_pal_data_parts) + "}"

    # Build richer detail data for modal (name, src, cvd, colors with labels)
    _pal_detail_parts = []
    for _pid, (_name, _src, _cvd, _colors) in _PAL_QUAL.items():
        _cl = "[" + ",".join(f'{{"hex":"{c}","label":"{l}"}}' for c, l in _colors) + "]"
        _cvd_s = "true" if _cvd else "false"
        _pal_detail_parts.append(f'"{_pid}":{{"name":"{_name}","src":"{_src}","cvd":{_cvd_s},"colors":{_cl}}}')
    for _pid, (_name, _src, _cvd, _colors) in _PAL_GENO.items():
        _cl = "[" + ",".join(f'{{"hex":"{c}","label":"{l}"}}' for c, l in _colors) + "]"
        _cvd_s = "true" if _cvd else "false"
        _pal_detail_parts.append(f'"{_pid}":{{"name":"{_name}","src":"{_src}","cvd":{_cvd_s},"colors":{_cl}}}')
    _pal_detail_js = "{" + ",".join(_pal_detail_parts) + "}"

    return f'''
<div class="palette-accordion" id="palettes">
  <button class="pal-toggle" onclick="togglePalettes()" id="pal-toggle-btn">
    <span>🎨 Color Palettes</span>
    <span class="pal-toggle-meta">27 palettes · CVD-safe options · Click to copy hex</span>
    <span class="pal-arrow" id="pal-arrow">▾</span>
  </button>
  <div class="pal-body" id="pal-body">
    <div class="palette-filters">
      <button class="pal-filter-btn active" data-pfilter="all">All</button>
      <button class="pal-filter-btn" data-pfilter="true">CVD-safe only</button>
    </div>

    <h3 style="color:var(--ink);font-size:.95rem;margin:0 0 8px;padding:0;">Qualitative Palettes</h3>
    <p style="color:var(--ink-muted);font-size:.78rem;margin:0 0 14px;">Categorical / group comparisons — bar charts, line plots, scatter</p>
    <div class="palette-grid">{_q}</div>

    <h3 style="color:var(--ink);font-size:.95rem;margin:0 0 8px;padding:0;">Genomics & Bioinformatics</h3>
    <p style="color:var(--ink-muted);font-size:.78rem;margin:0 0 14px;">Specialized schemes for common genomic visualizations</p>
    <div class="palette-grid">{_g}</div>

    <h3 style="color:var(--ink);font-size:.95rem;margin:0 0 8px;padding:0;">Sequential & Diverging Colormaps</h3>
    <p style="color:var(--ink-muted);font-size:.78rem;margin:0 0 14px;">Continuous data — heatmaps, density. Use via <code>cmap='viridis'</code> in matplotlib.</p>
    <div style="overflow-x:auto;margin-bottom:28px;">
    <table class="palette-cmap">
    <thead><tr><th>Name</th><th>Label</th><th>Description</th><th>CVD</th><th>Preview</th></tr></thead>
    <tbody>{_t}</tbody>
    </table>
    </div>

    <div class="palette-submit" id="custom-palette-form">
      <h4>🎨 Submit a Custom Palette</h4>
      <div><label for="ps-name">Palette Name</label><input type="text" id="ps-name" placeholder="My Awesome Palette"></div>
      <div><label for="ps-source">Source (optional)</label><input type="text" id="ps-source" placeholder="e.g. Nature Methods 2023"></div>
      <div><label>Colors (hex, 5-10)</label>
        <div class="ps-colors" id="ps-colors">
          <input type="text" class="ps-color-input" placeholder="#1B9E77" maxlength="7">
          <input type="text" class="ps-color-input" placeholder="#D95F02" maxlength="7">
          <input type="text" class="ps-color-input" placeholder="#7570B3" maxlength="7">
          <input type="text" class="ps-color-input" placeholder="#E7298A" maxlength="7">
          <input type="text" class="ps-color-input" placeholder="#66A61E" maxlength="7">
        </div>
      </div>
      <div><label for="ps-desc">Description</label><textarea id="ps-desc" rows="2" placeholder="What is this palette good for?"></textarea></div>
      <button class="ps-go" onclick="submitCustomPalette()">Submit Palette</button>
    </div>
  </div>
</div>

<div class="palette-detail-overlay" id="palette-detail-overlay" onclick="closePaletteDetail(event)">
  <div class="palette-detail-box" onclick="event.stopPropagation()">
    <button class="pd-close" onclick="closePaletteDetail(event)">&times;</button>
    <h3 id="pd-name"></h3>
    <div class="pd-src" id="pd-src"></div>
    <div id="pd-cvd-badge"></div>
    <div class="pd-swatches" id="pd-swatches"></div>
    <button class="pd-copy-all" onclick="copyAllPaletteColors()">📋 Copy all colors</button>
    <div class="pd-code" id="pd-code"></div>
  </div>
</div>

<script>
function togglePalettes() {{
  var body = document.getElementById('pal-body');
  var arrow = document.getElementById('pal-arrow');
  var btn = document.getElementById('pal-toggle-btn');
  if(body.style.maxHeight && body.style.maxHeight !== '0px') {{
    body.style.maxHeight = '0px';
    body.style.overflow = 'hidden';
    arrow.textContent = '▾';
    btn.classList.remove('open');
  }} else {{
    body.style.maxHeight = 'none';
    var h = body.scrollHeight;
    body.style.maxHeight = '0px';
    body.offsetHeight;
    body.style.maxHeight = h + 'px';
    body.style.overflow = 'visible';
    arrow.textContent = '▴';
    btn.classList.add('open');
  }}
}}
// Palette filter
document.querySelectorAll('.pal-filter-btn').forEach(function(btn){{
  btn.addEventListener('click', function(){{
    document.querySelectorAll('.pal-filter-btn').forEach(function(b){{ b.classList.remove('active'); }});
    btn.classList.add('active');
    var cvd = btn.dataset.pfilter;
    document.querySelectorAll('.palette-card').forEach(function(c){{
      if(cvd === 'all') c.style.display = '';
      else c.style.display = (c.dataset.cvd === cvd) ? '' : 'none';
    }});
  }});
}});
function copyHex(el) {{
  var hex = el.dataset.hex || (el.querySelector('.pal-hex') || {{}}).textContent;
  if(hex) navigator.clipboard.writeText(hex).then(function(){{ showToast(_t('toast_copy_ok') + ': ' + hex); }}).catch(function(){{ showToast(_t('toast_copy_fail'), 'reject'); }});
}}
var PAL_DATA = {_pal_js};
var PAL_DETAIL = {_pal_detail_js};
var _curPalColors = [];
function copyPalette(el) {{
  var pid = el.dataset.pid;
  var c = PAL_DATA[pid];
  if(c) navigator.clipboard.writeText(c.join(', ')).then(function(){{ showToast(_t('toast_copy_ok') + ' ' + c.length + ' colors'); }}).catch(function(){{ showToast(_t('toast_copy_fail'), 'reject'); }});
}}
function openPaletteDetail(pid) {{
  var d = PAL_DETAIL[pid];
  if(!d) return;
  document.getElementById('pd-name').textContent = d.name;
  document.getElementById('pd-src').textContent = d.src;
  var cvdBadge = d.cvd ? '<span class="cvd-yes">✓ CVD-safe</span>' : '<span class="cvd-no">✗ Not CVD-safe</span>';
  document.getElementById('pd-cvd-badge').innerHTML = cvdBadge;
  var swHtml = '';
  _curPalColors = [];
  d.colors.forEach(function(c) {{
    _curPalColors.push(c.hex);
    swHtml += '<div class="pd-swatch" style="background:' + c.hex + '" data-hex="' + c.hex + '" onclick="event.stopPropagation();copyHex(this)"><span class="pd-hex-label">' + c.hex + '</span></div>';
  }});
  document.getElementById('pd-swatches').innerHTML = swHtml;
  var codeHtml = '<strong>Python:</strong><br><code>from brain.plotting.colors import get_palette\\npal = get_palette(&quot;' + pid + '&quot;)</code><br><br><strong>R:</strong><br><code>pal <- get_pal(&quot;' + pid + '&quot;)</code>';
  document.getElementById('pd-code').innerHTML = codeHtml;
  document.getElementById('palette-detail-overlay').classList.add('show');
}}
function closePaletteDetail(e) {{
  document.getElementById('palette-detail-overlay').classList.remove('show');
}}
function copyAllPaletteColors() {{
  if(_curPalColors.length) navigator.clipboard.writeText(_curPalColors.join(', ')).then(function(){{ showToast(_t('toast_copy_ok') + ' ' + _curPalColors.length + ' colors'); }}).catch(function(){{ showToast(_t('toast_copy_fail'), 'reject'); }});
}}
function submitCustomPalette() {{
  var name = document.getElementById('ps-name').value.trim();
  if(!name) {{ showToast(_t('toast_enter_palette_name'), 'reject'); return; }}
  var inputs = document.querySelectorAll('#ps-colors .ps-color-input');
  var colors = [];
  inputs.forEach(function(inp) {{ var v = inp.value.trim(); if(v && /^#[0-9A-Fa-f]{{3,8}}$/.test(v)) colors.push(v); }});
  if(colors.length < 3) {{ showToast(_t('toast_min_colors'), 'reject'); return; }}
  var source = document.getElementById('ps-source').value.trim();
  var desc = document.getElementById('ps-desc').value.trim();
  fetch('/api/gallery/palette_submit', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{name: name, colors: colors, description: desc, source: source}})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if(d.ok) showToast(_t('toast_palette_submitted'));
    else showToast(_t('toast_error') + ': ' + (d.error||'Unknown'), 'reject');
  }}).catch(function() {{ showToast(_t('toast_network_error'), 'reject'); }});
}}
</script>
'''


def gallery_page() -> str:
    """Render the plotting library gallery page with interactive actions."""
    import yaml, json as _json, os as _os
    _plotting_dir = os.environ.get("BRAIN_PLOTTING_DIR", "")
    _catalog_path = _os.path.join(_plotting_dir, "catalog.yaml")

    try:
        with open(_catalog_path) as _f:
            _catalog = _normalize_catalog(yaml.safe_load(_f) or {})
    except Exception:
        _catalog = {"charts": []}

    # Build demo/interactive maps from catalog (no hardcoded dicts needed)
    _demo_files = {}
    _interactive_files = {}
    for _c in _catalog.get("charts", []):
        _n = _c.get("name", "")
        if _c.get("demo"):
            # Verify file exists
            if _os.path.exists(_os.path.join(_plotting_dir, _c["demo"])):
                _demo_files[_n] = _c["demo"]
        if _c.get("interactive"):
            if _os.path.exists(_os.path.join(_plotting_dir, _c["interactive"])):
                _interactive_files[_n] = _c["interactive"]

    # Load feedback log and compute approved charts (latest action = 'approve')
    _approved_charts = set()
    _feedback_path = _os.path.join(_plotting_dir, "gallery_feedback.jsonl")
    _latest_action: dict[str, str] = {}
    try:
        with open(_feedback_path) as _ff:
            for _line in _ff:
                _line = _line.strip()
                if not _line:
                    continue
                try:
                    _entry = _json.loads(_line)
                    _latest_action[_entry["chart"]] = _entry["action"]
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    for _chart_name, _act in _latest_action.items():
        if _act == "approve":
            _approved_charts.add(_chart_name)

    # Category groups for cleaner filter UI (map tags → broad chart-type categories)
    _CATEGORY_GROUPS = {
        # tag → 图表类型大类
        "散点": "散点图", "差异表达": "散点图", "GWAS/QTL": "散点图", "富集": "散点图",
        "降维": "散点图", "位点标注": "散点图", "检验": "散点图", "配对比较": "散点图",
        "组成": "散点图", "3D": "散点图", "单细胞": "散点图", "APA": "散点图",

        "线图/曲线": "线图/曲线", "生存": "线图/曲线", "分类": "线图/曲线",

        "分布": "分布图", "箱线": "分布图", "云雨": "分布图", "山峦": "分布图",

        "热图": "热图", "聚类": "热图", "相关性": "热图", "脑区": "热图", "环状": "热图",

        "柱状图": "柱状图", "分组比较": "柱状图", "双向": "柱状图",
        "面积图": "柱状图",

        "网络/关系": "网络/关系图", "互作": "网络/关系图", "弦图": "网络/关系图",
        "冲积": "网络/关系图", "桑基": "网络/关系图",

        "集合": "集合图", "交集": "集合图",

        "圈图": "圈图", "基因组": "圈图",

        "基因组结构": "基因组图", "基因簇": "基因组图", "进化树": "基因组图",
        "共线性": "基因组图", "突变": "基因组图", "标注": "基因组图",

        "临床": "临床图", "森林图": "临床图", "预后": "临床图",

        "雷达图": "雷达图", "多维": "雷达图",
    }

    chart_cards = ""
    for c in _catalog.get("charts", []):
        name = c.get("name", "")
        title = c.get("title", name)
        desc = c.get("description", "")
        tags = c.get("tags", [])
        tier = c.get("tier", "P2")
        status = c.get("status", "planned")
        tpl_path = c.get("template", "")
        has_template = (
            _os.path.exists(_os.path.join(_plotting_dir, "templates", f"{name}.py"))
            or _os.path.exists(_os.path.join(_plotting_dir, "templates", f"{name}.R"))
            or (tpl_path and _os.path.exists(_os.path.join(_plotting_dir, tpl_path)))
        )
        img_file = _demo_files.get(name)
        interactive_file = _interactive_files.get(name)

        # Map tags to broader categories for filtering
        categories = set()
        for t in tags:
            categories.add(_CATEGORY_GROUPS.get(t, "其他"))

        card_class = ("has-demo has-approved" if img_file and name in _approved_charts
                      else "has-demo" if img_file else "no-demo")
        status_icon = "✅" if status == "done" else "📋"
        badges_html = f'<div class="badge-row"><span class="tier-badge tier-{tier}">{tier}</span><span class="status-icon">{status_icon}</span></div>'
        if interactive_file:
            badges_html = f'<div class="badge-row"><span class="tier-badge tier-{tier}">{tier}</span><span class="status-icon">{status_icon}</span><span class="interactive-indicator">↗</span></div>'

        if img_file:
            img_url = f"/gallery/static/{img_file}"
            preview = f'<div class="card-img">{badges_html}<img src="{img_url}" loading="lazy"></div>'
        else:
            preview = f'<div class="card-img" style="color:var(--ink-dim);font-size:13px;display:flex;align-items:center;justify-content:center;">{badges_html}<span class="planned-placeholder" data-i18n="gl_planned">Planned</span></div>'

        tags_html = "".join(f'<span class="tag">{_html.escape(t)}</span>' for t in tags[:3])
        # Add input_shape as a distinguishing tag
        data_type = c.get("data_type") or c.get("input_shape", "")
        if data_type:
            tags_html = f'<span class="tag tag-shape">{_html.escape(data_type)}</span>' + tags_html

        safe_name = _html.escape(name)
        # Build footer pills: Done/Planned + template language + Interactive
        pills = []
        if status == "done":
            pills.append('<span class="pill pill-done">Done</span>')
        else:
            pills.append('<span class="pill pill-planned">Planned</span>')
        if has_template:
            ext = tpl_path.rsplit(".", 1)[-1].lower() if tpl_path else ""
            if ext == "py" or _os.path.exists(_os.path.join(_plotting_dir, "templates", f"{name}.py")):
                pills.append('<span class="pill pill-template">Python</span>')
            if ext == "r" or _os.path.exists(_os.path.join(_plotting_dir, "templates", f"{name}.R")):
                pills.append('<span class="pill pill-template">R</span>')
            if ext not in ("py", "r") and not _os.path.exists(_os.path.join(_plotting_dir, "templates", f"{name}.py")) and not _os.path.exists(_os.path.join(_plotting_dir, "templates", f"{name}.R")):
                pills.append('<span class="pill pill-template">Template</span>')
        if interactive_file:
            pills.append('<span class="pill pill-interactive">Interactive</span>')
        footer_html = f'<div class="card-footer">{"".join(pills)}</div>'

        data_attrs = f'data-tags="{" ".join(tags)}" data-category="{" ".join(categories)}" data-tier="{tier}" data-status="{status}"'
        chart_cards += (
            f'<a href="/gallery/{safe_name}" class="gallery-card-link" {data_attrs}>'
            f'<div class="gallery-card {card_class}">'
            f'{preview}'
            f'<div class="card-info"><h3>{_html.escape(title)}</h3>'
            f'<div class="desc">{_html.escape(desc[:120])}</div>'
            f'<div class="tags">{tags_html}</div></div>'
            f'{footer_html}'
            f'</div></a>'
        )

    # Filter by broad categories instead of raw tags
    _all_categories = sorted(set(
        _CATEGORY_GROUPS.get(t, "其他")
        for c in _catalog.get("charts", [])
        for t in c.get("tags", [])
    ))
    _tier_options = ["P0", "P1", "P2"]
    filter_btns = '<button class="filter-btn active" data-filter="all">All</button>'
    filter_btns += ' <span class="filter-sep">│</span>'
    filter_btns += '<span class="filter-label">Tier</span>'
    for t in _tier_options:
        tiers_class = f'tier-{t}'
        filter_btns += f' <button class="filter-btn {tiers_class}" data-filter="tier-{t}" data-tier="{t}">{t}</button>'
    filter_btns += ' <span class="filter-sep">│</span>'
    filter_btns += '<span class="filter-label">Type</span>'
    for cat in _all_categories:
        filter_btns += f' <button class="filter-btn cat-btn" data-filter="cat-{_html.escape(cat)}">{_html.escape(cat)}</button>'

    # NOTE: JS goes in extra_js, NOT in the body f-string,
    # so that curly braces are not mangled by Python's f-string escaping.
    gallery_css = '''
<style>
/* ── Gallery Layout ── */
.gallery-container { max-width: 1280px; margin: 0 auto; padding: var(--sp-lg) var(--sp-md); }
.gallery-header { text-align: center; margin-bottom: 20px; }
.gallery-header h1 { color: var(--ink); font-size: 28px; font-weight: 700; letter-spacing: -0.5px; margin: 0 0 4px; }
.gallery-header p { color: var(--ink-dim); font-size: 13px; margin: 0; }

/* ── Stats Summary ── */
.gallery-stats { display: flex; gap: 16px; justify-content: center; margin-bottom: 18px; }
.stat-item { display: flex; flex-direction: column; align-items: center; padding: 8px 18px; background: var(--card); border: 1px solid var(--border-hover); border-radius: var(--r-md); min-width: 72px; }
.stat-item .stat-num { font-size: 22px; font-weight: 700; color: var(--ink); line-height: 1.1; }
.stat-item .stat-label { font-size: 10px; color: var(--ink-dim); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
.stat-done .stat-num { color: var(--success); }
.stat-p0 .stat-num { color: var(--danger); }
.stat-p1 .stat-num { color: var(--primary); }
.stat-p2 .stat-num { color: var(--ink-dim); }

/* ── Toolbar (search + submit) ── */
.gallery-toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
.search-wrap { position: relative; flex: 1; min-width: 200px; max-width: 400px; }
.search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--ink-dim); font-size: 14px; pointer-events: none; }
#gallery-search { width: 100%; padding: 7px 32px 7px 30px; border: 1px solid var(--border-hover); border-radius: var(--r-pill); background: var(--card); color: var(--ink); font-size: 13px; transition: all var(--duration) var(--ease-out); }
#gallery-search:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-muted); }
.search-clear { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); color: var(--ink-dim); cursor: pointer; font-size: 12px; display: none; padding: 2px 4px; border-radius: 3px; }
.search-clear:hover { color: var(--ink); }
.toolbar-actions { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.card-count { font-size: 12px; color: var(--ink-dim); white-space: nowrap; }

/* ── Filter Bar ── */
.filter-bar { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; align-items: center; }
.filter-section { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.filter-label { color: var(--ink-dim); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-right: 2px; }
.filter-sep { color: var(--border); font-size: 14px; margin: 0 6px; opacity: 0.4; }
.filter-btn { background: var(--card); border: 1px solid var(--border-hover); color: var(--ink-muted); padding: 5px 14px; border-radius: var(--r-pill); cursor: pointer; font-size: 12px; transition: all var(--duration) var(--ease-out); }
.filter-btn:hover { background: var(--card-hover); border-color: var(--primary); color: var(--ink); }
.filter-btn.active { background: var(--primary); border-color: var(--primary); color: var(--bg); }
.tier-P0.active { background: var(--danger); border-color: var(--danger); color: var(--bg); }
.tier-P1.active { background: var(--primary); border-color: var(--primary); color: var(--bg); }
.tier-P2.active { background: var(--ink-dim); border-color: var(--ink-dim); color: var(--ink); }

/* ── Card Grid ── */
.gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--sp-md); margin-top: var(--sp-md); }
.gallery-card-link { text-decoration: none; color: inherit; display: block; }
.gallery-card { background: var(--card); border: 1px solid var(--border-hover); border-radius: var(--r-md); overflow: hidden; transition: all 0.25s cubic-bezier(.4,0,.2,1); position: relative; }
.gallery-card:hover { border-color: var(--primary); transform: translateY(-4px); box-shadow: var(--shadow-lg); }
.gallery-card.has-demo { border-left: 3px solid var(--success); }
.gallery-card.no-demo { border-left: 3px solid var(--border-hover); opacity: 0.85; }
.gallery-card.no-demo:hover { opacity: 1; }

/* ── Card Image ── */
.card-img { background: var(--bg); min-height: 160px; display: flex; align-items: center; justify-content: center; padding: 8px; cursor: pointer; border-bottom: 1px solid var(--border); position: relative; overflow: hidden; }
.card-img img { max-width: 100%; max-height: 180px; object-fit: contain; transition: transform 0.3s ease; }
.gallery-card:hover .card-img img { transform: scale(1.04); }
.card-img .planned-placeholder { color: var(--ink-dim); font-size: 12px; text-align: center; padding: 16px; line-height: 1.4; }
.planned-placeholder::before { content: '📋'; display: block; font-size: 28px; margin-bottom: 6px; opacity: 0.5; }

/* ── Tier & Status Badges ── */
.badge-row { position: absolute; top: 8px; left: 8px; display: flex; gap: 4px; align-items: center; z-index: 2; }
.tier-badge { font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 3px; letter-spacing: 0.5px; }
.tier-badge.tier-P0 { background: var(--danger); color: var(--bg); }
.tier-badge.tier-P1 { background: var(--primary); color: var(--bg); }
.tier-badge.tier-P2 { background: var(--ink-dim); color: var(--ink-muted); }
.status-icon { font-size: 11px; filter: grayscale(0.2); }
.interactive-indicator { font-size: 10px; color: var(--info); }

/* ── Card Info ── */
.card-info { padding: 10px 14px 6px; }
.card-info h3 { font-size: 14px; color: var(--ink); margin: 0 0 3px; font-weight: 600; }
.card-info h3 a:hover { color: var(--primary); }
.card-info .desc { font-size: 12px; color: var(--ink-muted); margin-bottom: 6px; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card-info .tags { display: flex; gap: 4px; flex-wrap: wrap; }
.card-info .tag { font-size: 10px; background: var(--surface); border: 1px solid var(--border-hover); color: var(--ink-muted); padding: 1px 7px; border-radius: 10px; }
.card-info .tag.tag-shape { background: var(--primary-muted); border-color: var(--primary); color: var(--primary); font-weight: 600; }

/* ── Action Buttons ── */
.btn-act { border: 1px solid var(--border-hover); border-radius: 4px; padding: 3px 10px; font-size: 11px; cursor: pointer; transition: all var(--duration) var(--ease-out); background: transparent; color: var(--ink-muted); }
.btn-ok:hover { background: var(--success-muted); border-color: var(--success); color: var(--success); }
.btn-edit:hover { background: var(--primary-muted); border-color: var(--primary); color: var(--primary); }
.btn-no:hover { background: var(--danger-muted); border-color: var(--danger); color: var(--danger); }
.btn-interactive { border-color: var(--primary); color: var(--primary); }
.btn-interactive:hover { background: var(--primary-muted); }

/* ── Card footer: tier + status pills ── */
.card-footer { display: flex; gap: 6px; padding: 6px 14px 10px; align-items: center; flex-wrap: wrap; }
.card-footer .pill { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.pill-done { background: var(--success-muted); color: var(--success); }
.pill-planned { background: var(--surface); color: var(--ink-dim); border: 1px solid var(--border-hover); }
.pill-interactive { background: var(--info-muted); color: var(--info); }
.pill-template { background: var(--primary-muted); color: var(--primary); }

/* ── Suggest Input ── */
.suggest-input { margin: 4px 14px 10px; }
.suggest-input textarea { width: 100%; padding: 6px 8px; border-radius: 4px; border: 1px solid var(--border-hover); background: var(--bg); color: var(--ink); font-size: 12px; min-height: 50px; resize: vertical; box-sizing: border-box; }
.suggest-input textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-muted); }
.suggest-input button { margin-top: 4px; padding: 4px 12px; border-radius: 4px; background: var(--primary); color: var(--bg); border: none; font-size: 11px; cursor: pointer; }

/* ── Modal ── */
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; justify-content: center; align-items: center; }
.modal-overlay.show { display: flex; }
.modal-overlay img { max-width: 92vw; max-height: 88vh; object-fit: contain; background: var(--card); border-radius: var(--r-md); box-shadow: var(--shadow-xl); }
.modal-overlay .close { position: absolute; top: 16px; right: 24px; color: var(--ink); font-size: 32px; cursor: pointer; opacity: 0.7; transition: opacity var(--duration); }
.modal-overlay .close:hover { opacity: 1; }
.iframe-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 1100; }
.iframe-modal.show { display: flex; flex-direction: column; }
.iframe-modal .iframe-header { display: flex; justify-content: space-between; align-items: center; padding: 8px var(--sp-md); background: var(--card); border-bottom: 1px solid var(--border-hover); }
.iframe-modal .iframe-header h3 { color: var(--ink); font-size: 14px; margin: 0; }
.iframe-modal .iframe-close { color: var(--ink-muted); font-size: 22px; cursor: pointer; padding: 0 8px; }
.iframe-modal .iframe-close:hover { color: var(--danger); }
.iframe-modal iframe { flex: 1; border: none; width: 100%; }

/* ── Toast ── */
.toast { position: fixed; bottom: 24px; right: 24px; padding: 10px 20px; border-radius: var(--r-md); color: var(--bg); font-size: 13px; font-weight: 500; z-index: 2000; opacity: 0; transition: opacity 0.3s; pointer-events: none; box-shadow: var(--shadow-md); background: var(--ink); }
.toast.show { opacity: 1; }
.toast.approve { background: var(--success); }
.toast.suggest { background: var(--primary); }
.toast.reject { background: var(--danger); }

/* ── Submit Figure ── */
.submit-form { display: none; margin-top: 10px; margin-bottom: 12px; }
.submit-form.open { display: block; }
.submit-toggle-btn { background: var(--card); border: 1px solid var(--border-hover); color: var(--ink-muted); padding: 6px 16px; border-radius: var(--r-pill); cursor: pointer; font-size: 12px; transition: all var(--duration) var(--ease-out); }
.submit-toggle-btn:hover { background: var(--card-hover); border-color: var(--primary); color: var(--primary); }
.submit-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-width: 600px; margin: 0 auto; }
.submit-grid label, .submit-notes-row label { color: var(--ink-muted); font-size: 11px; display: block; margin-bottom: 2px; }
.submit-grid input[type="text"], .submit-grid input[type="file"] { width: 100%; padding: 6px 8px; border: 1px solid var(--border-hover); border-radius: 4px; background: var(--bg); color: var(--ink); font-size: 12px; box-sizing: border-box; }
.submit-grid input[type="file"] { padding: 4px; }
.submit-notes-row { max-width: 600px; margin: 6px auto 0; }
.submit-notes-row textarea { width: 100%; padding: 6px 8px; border: 1px solid var(--border-hover); border-radius: 4px; background: var(--bg); color: var(--ink); font-size: 12px; resize: vertical; box-sizing: border-box; min-height: 40px; }
.submit-actions { max-width: 600px; margin: 6px auto 0; text-align: right; }
.submit-go { padding: 6px 16px; border-radius: 4px; background: var(--primary); color: var(--bg); border: none; font-size: 12px; cursor: pointer; }

/* ── Approved State ── */
.has-approved { border-left-color: var(--success) !important; }
.approved-badge { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; background: var(--success); color: white; font-size: 11px; font-weight: 700; margin-right: 4px; }

/* ── Color Palettes Module (Accordion) ── */
.palette-accordion { margin: 0 0 8px; border-radius: var(--r-lg); border: 1px solid var(--border); background: var(--surface); overflow: visible; }
.pal-toggle { width: 100%; display: flex; align-items: center; gap: 12px; padding: 12px 18px; border: none; background: none; cursor: pointer; color: var(--ink); font-size: .95rem; font-weight: 600; transition: background var(--duration); border-radius: var(--r-lg); }
.pal-toggle:hover { background: var(--card); }
.pal-toggle.open { border-radius: var(--r-lg) var(--r-lg) 0 0; }
.pal-toggle-meta { font-size: .75rem; font-weight: 400; color: var(--ink-muted); flex: 1; }
.pal-arrow { font-size: .8rem; color: var(--ink-muted); transition: transform var(--duration); }
.pal-body { max-height: 0px; overflow: hidden; transition: max-height .35s ease, padding .35s ease; padding: 0 18px; }
.palette-accordion:has(.pal-body[style*="max-height"]:not([style*="0px"])) .pal-body { padding: 8px 18px 18px; }
.palette-filters { display: flex; gap: 8px; justify-content: center; margin-bottom: 20px; }
.pal-filter-btn { padding: 5px 14px; border-radius: var(--r-md); border: 1px solid var(--border); background: var(--surface); color: var(--ink-muted); cursor: pointer; font-size: .8rem; transition: all var(--duration); }
.pal-filter-btn:hover { border-color: var(--primary); color: var(--primary); }
.pal-filter-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.palette-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; margin-bottom: 28px; }
.palette-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--r-md); padding: 14px; transition: border-color var(--duration), box-shadow var(--duration); cursor: pointer; }
.palette-card:hover { border-color: var(--primary); box-shadow: 0 4px 16px rgba(167,139,250,.1); }
.pal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.pal-name { font-size: .95rem; font-weight: 600; color: var(--ink); }
.cvd-yes { background: #009E7322; color: #00A087; border: 1px solid #009E7344; font-size: .68rem; padding: 2px 7px; border-radius: 10px; }
.cvd-no { background: #DC000022; color: #DC0000; border: 1px solid #DC000044; font-size: .68rem; padding: 2px 7px; border-radius: 10px; }
.pal-src { font-size: .7rem; color: var(--ink-dim); margin-bottom: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pal-swatches { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
.pal-swatch { width: 34px; height: 34px; border-radius: 5px; cursor: pointer; position: relative; transition: transform var(--duration); border: 1px solid rgba(255,255,255,.08); display: flex; align-items: flex-end; justify-content: center; }
.pal-swatch:hover { transform: scale(1.18); z-index: 1; box-shadow: 0 2px 8px rgba(0,0,0,.35); }
.pal-hex { font-size: .5rem; color: #000; background: rgba(255,255,255,.88); padding: 1px 3px; border-radius: 2px; opacity: 0; transition: opacity var(--duration); margin-bottom: 2px; font-family: var(--font-mono); }
.pal-swatch:hover .pal-hex { opacity: 1; }
.pal-footer { border-top: 1px solid var(--border); padding-top: 6px; }
.pal-copy { font-size: .7rem; cursor: pointer; color: var(--primary); padding: 2px 6px; border-radius: 4px; transition: background var(--duration), color var(--duration); }
.pal-copy:hover { background: var(--primary); color: #fff; }
.palette-cmap { width: 100%; border-collapse: collapse; font-size: .82rem; margin-bottom: 28px; }
.palette-cmap th { text-align: left; padding: 6px 8px; border-bottom: 2px solid var(--border); color: var(--ink-muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .5px; }
.palette-cmap td { padding: 6px 8px; border-bottom: 1px solid var(--border); color: var(--ink); }
.cmap-bar { height: 22px; border-radius: 4px; min-width: 120px; }
/* ── Palette Detail Modal ── */
.palette-detail-overlay { display:none; position:fixed; inset:0; z-index:9999; background:rgba(0,0,0,.55); backdrop-filter:blur(4px); justify-content:center; align-items:center; }
.palette-detail-overlay.show { display:flex; }
.palette-detail-box { background:var(--card); border:1px solid var(--border); border-radius:var(--r-lg); padding:28px 32px; max-width:560px; width:92vw; max-height:88vh; overflow-y:auto; position:relative; box-shadow:0 20px 60px rgba(0,0,0,.35); }
.palette-detail-box .pd-close { position:absolute; top:10px; right:14px; font-size:1.4rem; cursor:pointer; color:var(--ink-muted); background:none; border:none; }
.palette-detail-box .pd-close:hover { color:var(--ink); }
.palette-detail-box h3 { color:var(--ink); font-size:1.1rem; font-weight:700; margin:0 0 2px; }
.pd-src { color:var(--ink-dim); font-size:.75rem; margin-bottom:10px; }
.pd-swatches { display:flex; flex-wrap:wrap; gap:6px; margin:14px 0; }
.pd-swatch { width:64px; height:64px; border-radius:var(--r-md); border:1px solid var(--border); display:flex; align-items:flex-end; justify-content:center; cursor:pointer; transition:transform var(--duration); }
.pd-swatch:hover { transform:scale(1.12); }
.pd-swatch .pd-hex-label { font-size:.6rem; color:#000; background:rgba(255,255,255,.88); padding:1px 4px; border-radius:2px; margin-bottom:3px; font-family:var(--font-mono); }
.pd-copy-all { background:var(--primary); color:#fff; border:none; padding:7px 18px; border-radius:var(--r-md); cursor:pointer; font-size:.82rem; transition:opacity var(--duration); }
.pd-copy-all:hover { opacity:.85; }
.pd-code { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-md); padding:10px 14px; margin-top:14px; font-family:var(--font-mono); font-size:.78rem; color:var(--ink); white-space:pre-wrap; }
.pd-code code { font-size:.78rem; }
/* ── Custom Palette Submit ── */
.palette-submit { background:var(--card); border:1px solid var(--border); border-radius:var(--r-md); padding:20px 24px; margin:28px 0; }
.palette-submit h4 { color:var(--ink); font-size:.95rem; font-weight:600; margin:0 0 14px; }
.palette-submit label { color:var(--ink-muted); font-size:.78rem; display:block; margin-bottom:4px; }
.palette-submit input[type="text"], .palette-submit textarea { width:100%; background:var(--surface); border:1px solid var(--border); border-radius:var(--r-sm); padding:8px 10px; color:var(--ink); font-size:.82rem; margin-bottom:12px; box-sizing:border-box; }
.palette-submit input[type="text"]:focus, .palette-submit textarea:focus { border-color:var(--primary); outline:none; }
.ps-colors { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }
.ps-color-input { width:72px; }
.palette-submit .ps-go { background:var(--primary); color:#fff; border:none; padding:8px 20px; border-radius:var(--r-md); cursor:pointer; font-size:.82rem; }
</style>
'''

    # Stats summary
    _total = len(list(_catalog.get("charts", [])))
    _done = sum(1 for c in _catalog.get("charts", []) if c.get("status") == "done")
    _p0 = sum(1 for c in _catalog.get("charts", []) if c.get("tier") == "P0")
    _p1 = sum(1 for c in _catalog.get("charts", []) if c.get("tier") == "P1")
    _p2 = sum(1 for c in _catalog.get("charts", []) if c.get("tier") == "P2")
    stats_html = (
        '<div class="gallery-stats">'
        f'<div class="stat-item"><span class="stat-num">{_total}</span><span class="stat-label">Total</span></div>'
        f'<div class="stat-item stat-done"><span class="stat-num">{_done}</span><span class="stat-label">Done</span></div>'
        f'<div class="stat-item stat-p0"><span class="stat-num">{_p0}</span><span class="stat-label">P0</span></div>'
        f'<div class="stat-item stat-p1"><span class="stat-num">{_p1}</span><span class="stat-label">P1</span></div>'
        f'<div class="stat-item stat-p2"><span class="stat-num">{_p2}</span><span class="stat-label">P2</span></div>'
        '</div>'
    )

    body = (
        gallery_css +
        '<div class="gallery-container">'
        '<div class="gallery-header"><h1 data-i18n="gl_title">Sci-Fig Gallery</h1>'
        f'<p data-i18n="gl_subtitle">Scientific figure template library — view, approve, and contribute</p></div>'
        + stats_html +
        '<div class="gallery-toolbar">'
        '<div class="search-wrap">'
        '<span class="search-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span>'
        '<input type="text" id="gallery-search" data-i18n-ph="gl_search" placeholder="Search charts..." autocomplete="off">'
        '<span class="search-clear" id="search-clear" onclick="clearSearch()">✕</span>'
        '</div>'
        '<div class="toolbar-actions">'
        f'<span class="card-count" id="card-count" data-i18n-args data-i18n="gl_showing">Showing {_total} of {_total}</span>'
        '<button class="submit-toggle-btn" data-i18n="gl_submit" onclick="toggleSubmitForm()">+ Submit</button>'
        '</div></div>'
        '<div class="submit-form" id="submit-form">'
        '<div class="submit-grid">'
        '<div><label data-i18n="gl_image_url">Image URL</label><input type="text" id="submit-url" data-i18n-ph="gl_image_url_ph" placeholder="https://..."></div>'
        '<div><label data-i18n="gl_or_upload">Or Upload</label><input type="file" id="submit-file" accept="image/*"></div>'
        '</div>'
        '<div class="submit-notes-row"><label data-i18n="gl_notes">Notes</label>'
        '<textarea id="submit-notes" rows="2" data-i18n-ph="gl_notes_ph" placeholder="Figure type, paper source, what you like..."></textarea></div>'
        '<div class="submit-actions"><button class="submit-go" data-i18n="gl_submit_btn" onclick="submitFigure()">Submit</button></div>'
        '</div>'
        '<div class="filter-bar">' + filter_btns + '</div>'
        + _build_palettes_section()
        + '<div class="gallery-grid">' + chart_cards + '</div>'
        + '<div class="modal-overlay" id="modal" onclick="closeModal()"><span class="close">&times;</span>'
        '<img id="modal-img" src=""></div>'
        '<div class="iframe-modal" id="iframe-modal">'
        '<div class="iframe-header"><h3 id="iframe-title" data-i18n="gl_interactive">Interactive Chart</h3><span class="iframe-close" onclick="closeInteractive()">&times;</span></div>'
        '<iframe id="iframe-chart" src="" sandbox="allow-scripts allow-same-origin"></iframe>'
        '</div>'
        '<div class="toast" id="toast"></div>'
        '</div>'
    )

    gallery_js = """
// Interactive chart URL mapping (name -> HTML path)
var INTERACTIVE_MAP = %s;

function openModal(img) {
  document.getElementById('modal-img').src = img.src;
  document.getElementById('modal').classList.add('show');
}
function closeModal() {
  document.getElementById('modal').classList.remove('show');
}
function openInteractive(name) {
  var url = INTERACTIVE_MAP[name];
  if (!url) { showToast(_t('toast_no_interactive'), 'reject'); return; }
  document.getElementById('iframe-title').textContent = _t('gl_interactive') + ': ' + name;
  document.getElementById('iframe-chart').src = '/gallery/static/' + url;
  document.getElementById('iframe-modal').classList.add('show');
}
function closeInteractive() {
  document.getElementById('iframe-modal').classList.remove('show');
  document.getElementById('iframe-chart').src = '';
}
function showToast(msg, type) {
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (type ? ' ' + type : '') + ' show';
  setTimeout(function(){ t.classList.remove('show'); }, 2500);
}
function feedback(chart, action, ev) {
  if (action === 'suggest') {
    var card = (ev || event).target.closest('.gallery-card');
    var existing = card.querySelector('.suggest-input');
    if (existing) { existing.remove(); return; }
    var div = document.createElement('div');
    div.className = 'suggest-input';
    var ta = document.createElement('textarea');
    ta.id = 'suggest-' + chart;
    ta.placeholder = 'Your suggestion...';
    div.appendChild(ta);
    var btn = document.createElement('button');
    btn.textContent = _t('gl_submit');
    btn.onclick = function(){ submitSuggest(chart); };
    div.appendChild(btn);
    card.appendChild(div);
    return;
  }
  fetch('/api/gallery/feedback', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({chart: chart, action: action, suggestion: ''}),
    credentials: 'same-origin'
  }).then(function(r) {
if (r.ok) { showToast(chart + (action === 'approve' ? ' ✓ ' + _t('toast_approved') : ' ✕ ' + _t('toast_rejected')), action); }
    else { showToast(_t('toast_error') + ': ' + r.status, 'reject'); }
  }
  showToast(chart + (action === 'approve' ? ' ✓ ' + _t('toast_approved') : ' ✕ ' + _t('toast_rejected')), action);
  });
}
function submitSuggest(chart) {
  var textarea = document.getElementById('suggest-' + chart);
  var text = textarea ? textarea.value.trim() : '';
  if (!text) { showToast(_t('toast_enter_suggestion'), 'reject'); return; }
  fetch('/api/gallery/feedback', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({chart: chart, action: 'suggest', suggestion: text}),
    credentials: 'same-origin'
  }).then(function(r) {
    if (r.ok) { showToast(chart + ' ✓ ' + _t('toast_suggestion_saved'), 'suggest'); }
  }).catch(function() {
    showToast(chart + ' ✓ ' + _t('toast_suggestion_noted'), 'suggest');
  });
  var input = textarea.closest('.suggest-input');
  if (input) input.remove();
}
// Submit figure for analysis
function toggleSubmitForm() {
  var form = document.getElementById('submit-form');
  form.classList.toggle('open');
}
function submitFigure() {
  var urlInput = document.getElementById('submit-url');
  var fileInput = document.getElementById('submit-file');
  var notesInput = document.getElementById('submit-notes');
  var url = urlInput.value.trim();
  var notes = notesInput.value.trim();
  var file = fileInput.files[0];

  if (!url && !file) {
    showToast(_t('toast_enter_url_or_file'), 'reject');
    return;
  }

  var formData = new FormData();
  if (url) formData.append('image_url', url);
  if (file) formData.append('file', file);
  if (notes) formData.append('notes', notes);

  fetch('/api/gallery/submit_figure', {
    method: 'POST',
    body: formData
  }).then(function(r) {
    if (r.ok) { return r.json(); }
    throw new Error('Server error: ' + r.status);
  }).then(function(data) {
    if (data.ok) {
      showToast(_t('toast_figure_submitted'), 'approve');
      urlInput.value = '';
      notesInput.value = '';
      fileInput.value = '';
      document.getElementById('submit-form').classList.remove('open');
    } else {
      showToast(data.error || _t('toast_error'), 'reject');
    }
  }).catch(function(e) {
    showToast(_t('toast_error') + ': ' + e.message, 'reject');
  });
}
// Search functionality
var searchInput = document.getElementById('gallery-search');
var searchClear = document.getElementById('search-clear');
if (searchInput) {
  searchInput.addEventListener('input', function() {
    var q = this.value.trim().toLowerCase();
    if (searchClear) searchClear.style.display = q ? 'block' : 'none';
    applyFilters();
  });
}
function clearSearch() {
  if (searchInput) { searchInput.value = ''; }
  if (searchClear) searchClear.style.display = 'none';
  applyFilters();
}

function updateCardCount() {
  var total = document.querySelectorAll('.gallery-card-link').length;
  var visible = document.querySelectorAll('.gallery-card-link:not([style*="display: none"])').length;
  var el = document.getElementById('card-count');
  if (el) el.textContent = _t('gl_showing') + ' ' + visible + ' ' + _t('gl_of') + ' ' + total;
}

// Restore saved filter from localStorage
var currentFilter = 'all';
(function() {
  var saved = localStorage.getItem('gallery_filter');
  if (saved) {
    document.querySelectorAll('.filter-btn').forEach(function(b){ b.classList.remove('active'); });
    var btn = document.querySelector('.filter-btn[data-filter="' + saved + '"]');
    if (btn) {
      btn.classList.add('active');
      currentFilter = saved;
    }
  }
})();
document.querySelectorAll('.filter-btn').forEach(function(btn){
  btn.addEventListener('click', function() {
    document.querySelectorAll('.filter-btn').forEach(function(b){ b.classList.remove('active'); });
    this.classList.add('active');
    currentFilter = this.dataset.filter;
    localStorage.setItem('gallery_filter', currentFilter);
    applyFilters();
  });
});

function applyFilters() {
  var q = searchInput ? searchInput.value.trim().toLowerCase() : '';
  var f = currentFilter;
  document.querySelectorAll('.gallery-card-link').forEach(function(link){
    var matchFilter = false;
    var matchSearch = true;
    // Filter
    if (f === 'all') { matchFilter = true; }
    else if (f.startsWith('tier-')) { matchFilter = (link.dataset.tier === f.substring(5)); }
    else if (f.startsWith('cat-')) { matchFilter = (link.dataset.category && link.dataset.category.indexOf(f.substring(4)) >= 0); }
    else { matchFilter = (link.dataset.tags && link.dataset.tags.indexOf(f) >= 0); }
    // Search
    if (q) {
      var card = link.querySelector('.gallery-card') || link;
      var title = (card.querySelector('h3') || {}).textContent || '';
      var desc = (card.querySelector('.desc') || {}).textContent || '';
      var tags = link.dataset.tags || '';
      matchSearch = (title.toLowerCase().indexOf(q) >= 0 || desc.toLowerCase().indexOf(q) >= 0 || tags.toLowerCase().indexOf(q) >= 0);
    }
    link.style.display = (matchFilter && matchSearch) ? '' : 'none';
  });
  updateCardCount();
}
// Apply initial filters
applyFilters();
"""

    return _page("Sci-Fig Gallery", body, extra_js=gallery_js % _json.dumps(_interactive_files), nav_active="gallery")


# ---------------------------------------------------------------------------
# Gallery Detail Page
# ---------------------------------------------------------------------------

def gallery_detail_page(name: str) -> str:
    """Render a full detail page for a single chart in the gallery."""
    import yaml, json as _json, os as _os

    _plotting_dir = os.environ.get("BRAIN_PLOTTING_DIR", "")
    _catalog_path = _os.path.join(_plotting_dir, "catalog.yaml")

    # 1. Load catalog
    try:
        with open(_catalog_path) as _f:
            _catalog = _normalize_catalog(yaml.safe_load(_f) or {})
    except Exception:
        _catalog = {"charts": []}

    # Find chart entry by name
    chart = None
    for c in _catalog.get("charts", []):
        if c.get("name") == name:
            chart = c
            break

    if chart is None:
        return _page("Not Found",
                     '<div style="max-width:600px;margin:80px auto;text-align:center;color:var(--ink-muted);">'
                     '<h2 style="color:var(--ink);margin-bottom:8px;">Chart Not Found</h2>'
                     '<p>No chart with name "' + _html.escape(name) + '" exists in the catalog.</p>'
                     '<a href="/gallery" style="margin-top:16px;display:inline-block;">← Back to Gallery</a></div>', nav_active="gallery")

    title = chart.get("title", name)
    desc = chart.get("description", "")
    tags = chart.get("tags", [])
    tier = chart.get("tier", "P2")
    status = chart.get("status", "planned")
    data_type = chart.get("data_type", "")
    # Columns: chart-level 'columns' + data_types schema
    chart_cols = chart.get("columns", [])
    data_types_info = _catalog.get("data_types", {}).get(data_type, {})
    req_cols = data_types_info.get("required_columns", chart_cols)
    opt_cols = data_types_info.get("optional_columns", [])
    recommended_for = chart.get("recommended_for", [])
    references = chart.get("references", [])
    demo_file = chart.get("demo", "")

    # 2. Read feedback history
    _feedback_path = _os.path.join(_plotting_dir, "gallery_feedback.jsonl")
    feedback_entries = []
    is_approved = False
    try:
        with open(_feedback_path) as _f:
            for line in _f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = _json.loads(line)
                    if entry.get("chart") == name:
                        feedback_entries.append(entry)
                        if entry.get("action") == "approve":
                            is_approved = True
                except Exception:
                    pass
    except FileNotFoundError:
        pass

    # 3. Scan templates/ directory for .py and .R files matching chart name
    _templates_dir = _os.path.join(_plotting_dir, "templates")
    template_files = []
    for ext in (".py", ".R"):
        fname = f"{name}{ext}"
        fpath = _os.path.join(_templates_dir, fname)
        if _os.path.isfile(fpath):
            fsize = _os.path.getsize(fpath)
            lang = "Python" if ext == ".py" else "R"
            template_files.append({"filename": fname, "size": fsize, "lang": lang})

    # Also check the explicit template path from catalog
    tpl_path = chart.get("template", "")
    if tpl_path:
        full_tpl = _os.path.join(_plotting_dir, tpl_path)
        tpl_fname = _os.path.basename(tpl_path)
        if _os.path.isfile(full_tpl) and not any(t["filename"] == tpl_fname for t in template_files):
            fsize = _os.path.getsize(full_tpl)
            ext = _os.path.splitext(tpl_fname)[1].lower()
            lang = "Python" if ext == ".py" else "R"
            template_files.append({"filename": tpl_fname, "size": fsize, "lang": lang})

    # ── Build HTML ──

    # Header: back link, title, tier badge, status badge
    status_icon = "✅" if status == "done" else "📋"
    status_label = "Done" if status == "done" else "Planned"
    status_color = "var(--success)" if status == "done" else "var(--ink-dim)"
    approved_badge = (
        '<span style="display:inline-block;padding:2px 10px;border-radius:var(--r-pill);'
        'font-size:11px;font-weight:600;background:var(--success-muted);color:var(--success);'
        'margin-left:8px;">✓ Approved</span>'
        if is_approved else ""
    )

    header_html = (
        '<div style="max-width:900px;margin:0 auto;padding:var(--sp-lg) var(--sp-md);">'
        '<a href="/gallery" style="color:var(--primary);font-size:13px;display:inline-block;margin-bottom:16px;">'
        '← Back to Gallery</a>'
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">'
        f'<h1 style="font-size:24px;font-weight:700;color:var(--ink);margin:0;">{_html.escape(title)}</h1>'
        f'<span style="display:inline-block;padding:2px 8px;border-radius:3px;font-size:10px;'
        f'font-weight:700;letter-spacing:0.5px;background:{"var(--danger)" if tier == "P0" else "var(--primary)" if tier == "P1" else "var(--ink-dim)"};'
        f'color:{"var(--bg)" if tier != "P2" else "var(--ink-muted)"};">{tier}</span>'
        f'<span style="display:inline-block;padding:2px 8px;border-radius:var(--r-pill);font-size:11px;'
        f'background:{"var(--success-muted)" if status == "done" else "var(--card)"};'
        f'color:{status_color};">{status_icon} {status_label}</span>'
        f'{approved_badge}'
        '</div></div>'
    )

    # Image section — left column in two-column layout
    if demo_file and _os.path.isfile(_os.path.join(_plotting_dir, demo_file)):
        img_url = f"/gallery/static/{demo_file}"
        image_html = (
            '<div style="cursor:pointer;border-radius:var(--r-md);overflow:hidden;border:1px solid var(--border-hover);background:var(--bg);" '
            'onclick="document.getElementById(\'detail-modal\').classList.add(\'show\');'
            'document.getElementById(\'detail-modal-img\').src=this.querySelector(\'img\').src;">'
            f'<img src="{img_url}" style="width:100%;display:block;">'
            '</div>'
        )
    else:
        image_html = (
            '<div style="padding:48px 0;text-align:center;background:var(--card);border-radius:var(--r-md);border:1px dashed var(--border-hover);">'
            '<span style="color:var(--ink-dim);font-size:14px;">📋 No demo yet</span></div>'
        )

    # Metadata card
    meta_parts = []
    if desc:
        meta_parts.append(f'<div style="margin-bottom:12px;"><span style="color:var(--ink-muted);font-size:12px;font-weight:600;">Description</span>'
                          f'<p style="color:var(--ink);font-size:14px;margin-top:4px;line-height:1.6;">{_html.escape(desc)}</p></div>')
    if data_type:
        meta_parts.append(f'<div style="margin-bottom:12px;"><span style="color:var(--ink-muted);font-size:12px;font-weight:600;">Data Type</span>'
                          f'<p style="color:var(--ink);font-size:13px;margin-top:4px;">{_html.escape(str(data_type))}</p></div>')
    if req_cols:
        cols_html = "".join(f'<span style="display:inline-block;padding:2px 8px;margin:2px;background:var(--primary-muted);color:var(--primary);border-radius:var(--r-pill);font-size:11px;">{_html.escape(str(c))}</span>' for c in req_cols)
        meta_parts.append(f'<div style="margin-bottom:12px;"><span style="color:var(--ink-muted);font-size:12px;font-weight:600;">Required Columns</span>'
                          f'<div style="margin-top:4px;">{cols_html}</div></div>')
    if opt_cols:
        cols_html = "".join(f'<span style="display:inline-block;padding:2px 8px;margin:2px;background:var(--surface);color:var(--ink-muted);border-radius:var(--r-pill);font-size:11px;border:1px solid var(--border-hover);">{_html.escape(str(c))}</span>' for c in opt_cols)
        meta_parts.append(f'<div style="margin-bottom:12px;"><span style="color:var(--ink-muted);font-size:12px;font-weight:600;">Optional Columns</span>'
                          f'<div style="margin-top:4px;">{cols_html}</div></div>')
    if tags:
        tags_html = "".join(f'<span style="display:inline-block;padding:2px 8px;margin:2px;background:var(--surface);border:1px solid var(--border-hover);color:var(--ink-muted);border-radius:var(--r-pill);font-size:11px;">{_html.escape(t)}</span>' for t in tags)
        meta_parts.append(f'<div style="margin-bottom:12px;"><span style="color:var(--ink-muted);font-size:12px;font-weight:600;">Tags</span>'
                          f'<div style="margin-top:4px;">{tags_html}</div></div>')
    if recommended_for:
        rec_html = "".join(f'<li style="color:var(--ink);font-size:13px;margin:2px 0;">{_html.escape(str(r))}</li>' for r in recommended_for)
        meta_parts.append(f'<div style="margin-bottom:12px;"><span style="color:var(--ink-muted);font-size:12px;font-weight:600;">Recommended For</span>'
                          f'<ul style="margin:4px 0 0 16px;">{rec_html}</ul></div>')
    if references:
        ref_html = "".join(f'<li style="color:var(--ink);font-size:13px;margin:2px 0;">{_html.escape(str(r))}</li>' for r in references)
        meta_parts.append(f'<div style="margin-bottom:12px;"><span style="color:var(--ink-muted);font-size:12px;font-weight:600;">References</span>'
                          f'<ul style="margin:4px 0 0 16px;">{ref_html}</ul></div>')

    metadata_html = (
        '<div style="background:var(--card);border:1px solid var(--border-hover);border-radius:var(--r-md);'
        'padding:var(--sp-md);">'
        '<h2 style="font-size:15px;font-weight:600;color:var(--ink);margin-bottom:12px;">Details</h2>'
        + "".join(meta_parts) +
        '</div>'
    )

    # Templates section
    if template_files:
        tpl_rows = ""
        for idx, tf in enumerate(template_files):
            fsize_str = f'{tf["size"]:,} B' if tf["size"] < 1024 else f'{tf["size"] / 1024:.1f} KB'
            lang_color = "var(--success)" if tf["lang"] == "Python" else "var(--info)"
            lang_bg = "var(--success-muted)" if tf["lang"] == "Python" else "var(--info-muted)"
            safe_id = f"tpl-code-{idx}"
            tpl_rows += (
                f'<div style="border-bottom:1px solid var(--border);">'
                f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;">'
                f'<a href="/gallery/static/templates/{_html.escape(tf["filename"])}" '
                f'style="color:var(--primary);font-size:13px;font-weight:500;flex:1;'
                f'font-family:var(--font-mono);">{_html.escape(tf["filename"])}</a>'
                f'<span style="font-size:11px;color:var(--ink-dim);">{fsize_str}</span>'
                f'<span style="display:inline-block;padding:2px 8px;border-radius:var(--r-pill);'
                f'font-size:10px;font-weight:600;background:{lang_bg};color:{lang_color};">'
                f'{tf["lang"]}</span>'
                f'<button id="{safe_id}-btn" onclick="toggleCodePreview(\'{safe_id}\',\'{_html.escape(tf["filename"])}\')" '
                f'style="padding:2px 10px;border-radius:4px;border:1px solid var(--border-hover);'
                f'background:var(--card);color:var(--ink-muted);font-size:11px;cursor:pointer;'
                f'transition:all var(--duration) var(--ease-out);">▸ Code</button>'
                f'</div>'
                f'<div id="{safe_id}" style="display:none;border-top:1px solid var(--border);'
                f'background:var(--bg);max-height:320px;overflow:auto;">'
                f'<pre style="margin:0;padding:12px 14px;font-size:12px;line-height:1.5;'
                f'font-family:var(--font-mono);color:var(--ink);white-space:pre-wrap;overflow-x:auto;" '
                f'id="{safe_id}-pre">Loading...</pre>'
                f'</div></div>'
            )
        templates_html = (
            '<div style="background:var(--card);border:1px solid var(--border-hover);border-radius:var(--r-md);'
            'overflow:hidden;">'
            '<div style="padding:var(--sp-sm) var(--sp-md);border-bottom:1px solid var(--border-hover);">'
            '<h2 style="font-size:15px;font-weight:600;color:var(--ink);margin:0;">Template Files</h2></div>'
            + tpl_rows +
            '</div>'
        )
    else:
        templates_html = (
            '<div style="background:var(--card);border:1px solid var(--border-hover);border-radius:var(--r-md);'
            'padding:var(--sp-lg);text-align:center;">'
            '<h2 style="font-size:16px;font-weight:600;color:var(--ink);margin-bottom:8px;">Template Files</h2>'
            '<span style="color:var(--ink-dim);font-size:13px;">No template files found yet.</span></div>'
        )

    # Upload section
    upload_html = (
        '<div style="background:var(--card);border:1px solid var(--border-hover);border-radius:var(--r-md);'
        'padding:var(--sp-md);">'
        '<h2 style="font-size:15px;font-weight:600;color:var(--ink);margin-bottom:10px;">Upload Template</h2>'
        f'<form id="upload-form" enctype="multipart/form-data" '
        f'style="display:flex;flex-direction:column;gap:10px;">'
        f'<input type="hidden" name="chart_name" value="{_html.escape(name)}">'
        '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">'
        '<input type="file" name="file" accept=".py,.R,.zip" '
        'style="padding:6px;border:1px solid var(--border-hover);border-radius:4px;'
        'background:var(--bg);color:var(--ink);font-size:12px;flex:1;min-width:200px;">'
        '<input type="text" name="description" placeholder="Description (optional)" '
        'style="flex:2;min-width:200px;padding:6px 10px;border:1px solid var(--border-hover);'
        'border-radius:4px;background:var(--bg);color:var(--ink);font-size:12px;">'
        '</div>'
        '<div style="text-align:right;">'
        '<button type="submit" style="padding:6px 20px;border-radius:4px;background:var(--primary);'
        'color:var(--bg);border:none;font-size:12px;cursor:pointer;font-weight:500;">Upload</button>'
        '</div></form></div>'
    )

    # Feedback section grouped by action type
    fb_by_action = {"approve": [], "suggest": [], "reject": []}
    for fb in feedback_entries:
        act = fb.get("action", "suggest")
        if act not in fb_by_action:
            fb_by_action[act] = []
        fb_by_action[act].append(fb)

    fb_sections = ""
    action_labels = {"approve": ("Approvals", "var(--success)", "var(--success-muted)"),
                     "suggest": ("Suggestions", "var(--primary)", "var(--primary-muted)"),
                     "reject": ("Rejections", "var(--danger)", "var(--danger-muted)")}
    for act_key in ("approve", "suggest", "reject"):
        entries = fb_by_action.get(act_key, [])
        if not entries:
            continue
        label, color, bg = action_labels[act_key]
        fb_rows = ""
        for fb in entries:
            ts = fb.get("timestamp", fb.get("ts", ""))
            sug = fb.get("suggestion", "")
            fb_rows += (
                f'<div style="padding:8px 14px;border-bottom:1px solid var(--border);display:flex;gap:12px;align-items:flex-start;">'
                f'<span style="color:var(--ink-dim);font-size:11px;white-space:nowrap;min-width:140px;">{_html.escape(str(ts))}</span>'
                f'<span style="color:var(--ink);font-size:13px;flex:1;">{_html.escape(str(sug)) if sug else "—"}</span>'
                f'</div>'
            )
        fb_sections += (
            f'<div style="background:var(--card);border:1px solid var(--border-hover);border-radius:var(--r-md);'
            f'margin-bottom:12px;overflow:hidden;">'
            f'<div style="padding:10px 14px;border-bottom:1px solid var(--border-hover);display:flex;align-items:center;gap:8px;">'
            f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};"></span>'
            f'<span style="font-size:13px;font-weight:600;color:{color};">{label}</span>'
            f'<span style="font-size:11px;color:var(--ink-dim);margin-left:auto;">{len(entries)}</span>'
            f'</div>'
            f'{fb_rows}'
            f'</div>'
        )

    if not fb_sections:
        fb_sections = (
            '<div style="color:var(--ink-dim);font-size:13px;text-align:center;padding:20px 0;">'
            'No feedback recorded yet.</div>'
        )

    feedback_html = (
        '<div style="margin-bottom:var(--sp-md);">'
        '<h2 style="font-size:15px;font-weight:600;color:var(--ink);margin-bottom:10px;">Feedback History</h2>'
        + fb_sections +
        '</div>'
    )

    # Actions: Approve (if not approved), Suggest, Reject
    safe_name_js = name.replace("\\", "\\\\").replace("'", "\\'")
    approve_btn = (
        f'<button onclick="detailFeedback(\'approve\')" '
        f'style="padding:8px 20px;border-radius:4px;background:var(--success);color:var(--bg);'
        f'border:none;font-size:13px;cursor:pointer;font-weight:600;">✓ Approve</button>'
        if not is_approved else
        '<span style="display:inline-flex;align-items:center;gap:6px;padding:6px 16px;border-radius:4px;'
        'background:var(--success-muted);color:var(--success);font-size:13px;font-weight:600;'
        'border:1px solid var(--success);">✓ Approved</span>'
    )

    actions_html = (
        '<div style="background:var(--card);border:1px solid var(--border-hover);border-radius:var(--r-md);'
        'padding:var(--sp-md);">'
        f'<h2 style="font-size:15px;font-weight:600;color:var(--ink);margin-bottom:10px;" data-i18n="kh_actions">{_pt("kh_actions")}</h2>'
        '<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">'
        f'{approve_btn}'
        f'<button onclick="openSuggestBox()" '
        'style="padding:8px 20px;border-radius:4px;background:var(--primary-muted);color:var(--primary);'
        f'border:1px solid var(--primary);font-size:13px;cursor:pointer;font-weight:600;">{_pt("gl_suggest")}</button>'
        f'<button onclick="detailFeedback(\'reject\')" '
        'style="padding:8px 20px;border-radius:4px;background:var(--danger-muted);color:var(--danger);'
        f'border:1px solid var(--danger);font-size:13px;cursor:pointer;font-weight:600;">✕ {_pt("kh_reject")}</button>'
        '</div>'
        '<div id="suggest-box" style="display:none;margin-top:12px;">'
        f'<textarea id="suggest-text" placeholder="{_pt("gl_suggest_ph")}" '
        'style="width:100%;padding:8px;border-radius:4px;border:1px solid var(--border-hover);'
        'background:var(--bg);color:var(--ink);font-size:13px;min-height:80px;resize:vertical;'
        'box-sizing:border-box;"></textarea>'
        '<div style="text-align:right;margin-top:6px;">'
        '<button onclick="submitDetailSuggest()" '
        'style="padding:6px 16px;border-radius:4px;background:var(--primary);color:var(--bg);'
        'border:none;font-size:12px;cursor:pointer;">Submit Suggestion</button></div></div>'
        '</div>'
    )

    # Toast notification
    toast_html = '<div id="detail-toast" style="position:fixed;bottom:24px;right:24px;padding:10px 20px;border-radius:var(--r-md);color:var(--bg);font-size:13px;font-weight:500;z-index:2000;opacity:0;transition:opacity 0.3s;pointer-events:none;box-shadow:var(--shadow-md);"></div>'

    # Modal overlay for image zoom
    modal_html = (
        '<div id="detail-modal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;'
        'background:rgba(0,0,0,0.9);z-index:1000;justify-content:center;align-items:center;cursor:pointer;" '
        'onclick="this.classList.remove(\'show\');this.style.display=\'none\';">'
        '<span style="position:absolute;top:16px;right:24px;color:var(--ink);font-size:32px;cursor:pointer;opacity:0.7;">&times;</span>'
        '<img id="detail-modal-img" style="max-width:92vw;max-height:88vh;object-fit:contain;background:var(--card);'
        'border-radius:var(--r-md);box-shadow:var(--shadow-xl);">'
        '</div>'
    )

    # Detail page CSS (minimal - most styling is inline)
    detail_css = '<style>#detail-modal.show{display:flex!important}@media(max-width:640px){.detail-meta-grid,.detail-action-grid{grid-template-columns:1fr!important}}.CodeMirror{font-size:13px;font-family:var(--font-mono),"Fira Code",monospace;border:none;height:auto;min-height:200px;max-height:500px;}.CodeMirror-scroll{min-height:200px;}.cm-s-material-darker .CodeMirror-gutters{background:#1e1e2e!important;border-right:1px solid var(--border)!important;}.cm-s-material-darker{background:#1a1a2e!important;}</style>'

    # Assemble body — image full width on top, then Details | Template Files side by side
    _image_row = (
        '<div style="margin-bottom:var(--sp-md);">' + image_html + '</div>'
    )
    _meta_row = (
        '<div class="detail-meta-grid" style="display:grid;grid-template-columns:3fr 2fr;gap:var(--sp-md);margin-bottom:var(--sp-md);">'
        + metadata_html
        + templates_html
        + '</div>'
    )

    # Full-width sections below the two-column area
    # ── Live Editor section ──
    # Read first R template for pre-fill
    _default_code = "# Write your R code here\nlibrary(ggplot2)\n"
    _tpl_code = _default_code
    _first_r_tpl = None
    for tf in template_files:
        if tf["lang"] == "R":
            _first_r_tpl = tf["filename"]
            break
    if not _first_r_tpl:
        for ext in (".R", ".py"):
            for c in _catalog.get("charts", []):
                _tpl = c.get("template", "")
                if _tpl.endswith(ext):
                    _first_r_tpl = _tpl.split("/")[-1]
                    break
            if _first_r_tpl:
                break
    # Read template file content for pre-fill
    if _first_r_tpl:
        for _tf in template_files:
            if _tf["filename"] == _first_r_tpl:
                _fpath = _os.path.join(_templates_dir, _tf["filename"])
                try:
                    with open(_fpath) as _f:
                        _tpl_code = _f.read()
                except Exception:
                    pass
                break
    # Strip source() boilerplate (render endpoint handles it)
    import re as _re
    _tpl_code = _re.sub(r'suppressPackageStartupMessages\(\{[^}]*\}\)', '', _tpl_code, flags=_re.DOTALL)
    _tpl_code = _re.sub(r'tryCatch\(source\([^)]+\),\s*\n\s*error\s*=\s*function\([^)]*\)\s*source\([^)]+\)\)', '', _tpl_code, flags=_re.DOTALL)
    _tpl_code = _re.sub(r'source\("[^"]+"\)\s*\n?', '', _tpl_code)
    # Strip entire if(sys.nframe()==0) demo block (uses ggsave, not current device)
    _tpl_code = _re.sub(r'if\s*\(sys\.nframe\(\)\s*==\s*0\)\s*\{.*\}\s*$', '', _tpl_code, flags=_re.DOTALL)
    _tpl_code = _re.sub(r'\n{3,}', '\n\n', _tpl_code)
    _tpl_code = _tpl_code.strip()
    # Detect main plot function name and add demo call
    _plot_fn_match = _re.search(r'(\w+_plot)\s*<-\s*function', _tpl_code)
    _demo_fn = _plot_fn_match.group(1) if _plot_fn_match else 'plot'
    _data_fn_match = _re.search(r'(generate_\w+|mock_\w+)\s*<-\s*function', _tpl_code)
    _data_fn = _data_fn_match.group(1) if _data_fn_match else None
    if _data_fn:
        _tpl_code += f'\n\n# --- Demo (editable) ---\ndf <- {_data_fn}()\nprint({_demo_fn}(df))\n'
    else:
        _tpl_code += f'\n\n# --- Demo (editable) ---\nprint({_demo_fn}())\n'
    _tpl_code_json = _json.dumps(_tpl_code)

    _editor_toolbar = (
        '<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;'
        'border-bottom:1px solid var(--border-hover);flex-wrap:wrap;">'
        '<span style="font-size:14px;font-weight:600;color:var(--ink);">🧪 Live Editor</span>'
        '<span style="font-size:11px;color:var(--ink-dim);">Edit code → Run → Preview</span>'
        '<div style="margin-left:auto;display:flex;gap:8px;align-items:center;">'
        '<select id="editor-format" style="padding:4px 8px;border:1px solid var(--border-hover);'
        'border-radius:4px;background:var(--bg);color:var(--ink);font-size:12px;">'
        '<option value="png">PNG</option><option value="pdf">PDF</option></select>'
        '<button id="editor-run-btn" onclick="runEditorCode()" '
        'style="padding:6px 18px;border-radius:var(--r-md);background:var(--primary);color:#fff;'
        'border:none;font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:6px;'
        'transition:opacity var(--duration);">▶ Run</button>'
        '<button onclick="resetEditorCode()" '
        'style="padding:6px 12px;border-radius:var(--r-md);background:var(--card);color:var(--ink-muted);'
        'border:1px solid var(--border-hover);font-size:12px;cursor:pointer;">↺ Reset</button>'
        '</div></div>'
    )

    _editor_body = (
        '<div id="editor-container" style="border-bottom:1px solid var(--border-hover);"></div>'
    )

    _editor_preview = (
        '<div id="editor-preview" style="padding:16px;min-height:120px;text-align:center;">'
        '<div id="editor-preview-placeholder" style="color:var(--ink-dim);font-size:13px;padding:40px 0;">'
        'Click <strong>▶ Run</strong> to generate a preview</div>'
        '<img id="editor-preview-img" style="max-width:100%;display:none;border-radius:var(--r-md);'
        'border:1px solid var(--border-hover);cursor:pointer;" '
        'onclick="window.open(this.src,\'_blank\')" title="Click to open full size">'
        '<div id="editor-preview-status" style="display:none;margin-top:8px;font-size:12px;color:var(--ink-dim);"></div>'
        '<pre id="editor-preview-error" style="display:none;margin-top:8px;padding:12px;background:var(--danger-muted);'
        'color:var(--danger);border-radius:var(--r-sm);font-size:12px;white-space:pre-wrap;text-align:left;'
        'max-height:200px;overflow:auto;"></pre>'
        '</div>'
    )

    live_editor_html = (
        '<div style="background:var(--card);border:1px solid var(--border-hover);border-radius:var(--r-md);'
        'overflow:hidden;margin-bottom:var(--sp-md);">'
        + _editor_toolbar + _editor_body + _editor_preview +
        '</div>'
    )

    # Row 1: Actions (left) | Upload (right), Row 2: Feedback (full width)
    _bottom_grid = (
        '<div class="detail-action-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-md);margin-bottom:var(--sp-md);">'
        + actions_html
        + upload_html
        + '</div>'
        + feedback_html
    )

    body = (
        detail_css +
        header_html +
        '<div style="max-width:960px;margin:0 auto;padding:0 var(--sp-md) var(--sp-xl);">' +
        _image_row +
        _meta_row +
        live_editor_html +
        _bottom_grid +
        '</div>' +
        modal_html +
        toast_html
    )

    # JavaScript for the detail page
    detail_js = r"""
function showToast(msg, type) {
  var t = document.getElementById('detail-toast');
  t.textContent = msg;
  t.style.background = type === 'approve' ? 'var(--success)' : type === 'reject' ? 'var(--danger)' : 'var(--primary)';
  t.style.opacity = '1';
  setTimeout(function(){ t.style.opacity = '0'; }, 2500);
}

function detailFeedback(action) {
  if (action === 'suggest') { openSuggestBox(); return; }
  fetch('/api/gallery/feedback', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({chart: CHART_NAME, action: action, suggestion: ''}),
    credentials: 'same-origin'
  }).then(function(r) {
    if (r.ok) { showToast(CHART_NAME + (action === 'approve' ? ' ✓ ' + _t('toast_approved') : ' ✕ ' + _t('toast_rejected')), action); setTimeout(function(){ location.reload(); }, 1200); }
    else { showToast(_t('toast_error') + ': ' + r.status, 'reject'); }
  }).catch(function() {
    showToast(CHART_NAME + (action === 'approve' ? ' ✓ ' + _t('toast_approved') : ' ✕ ' + _t('toast_rejected')), action);
    setTimeout(function(){ location.reload(); }, 1200);
  });
}

function openSuggestBox() {
  var box = document.getElementById('suggest-box');
  box.style.display = box.style.display === 'none' ? 'block' : 'none';
  if (box.style.display === 'block') document.getElementById('suggest-text').focus();
}

function submitDetailSuggest() {
  var text = document.getElementById('suggest-text').value.trim();
  if (!text) { showToast(_t('toast_enter_suggestion'), 'reject'); return; }
  fetch('/api/gallery/feedback', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({chart: CHART_NAME, action: 'suggest', suggestion: text}),
    credentials: 'same-origin'
  }).then(function(r) {
    if (r.ok) { showToast(CHART_NAME + ' ✓ ' + _t('toast_suggestion_saved'), 'suggest'); setTimeout(function(){ location.reload(); }, 1200); }
    else { showToast(_t('toast_error') + ': ' + r.status, 'reject'); }
  }).catch(function() {
    showToast(CHART_NAME + ' ✓ ' + _t('toast_suggestion_noted'), 'suggest');
    setTimeout(function(){ location.reload(); }, 1200);
  });
}

// Upload form handler
document.getElementById('upload-form').addEventListener('submit', function(e) {
  e.preventDefault();
  var formData = new FormData(this);
  fetch('/api/gallery/upload_script', {
    method: 'POST',
    body: formData
  }).then(function(r) {
    if (r.ok) { showToast(_t('toast_upload_ok'), 'approve'); setTimeout(function(){ location.reload(); }, 1200); }
    else { showToast(_t('toast_upload_fail') + ': ' + r.status, 'reject'); }
  }).catch(function(err) {
    showToast(_t('toast_upload_fail') + ': ' + err.message, 'reject');
  });
});

// Modal close on escape
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    var m = document.getElementById('detail-modal');
    if (m) { m.classList.remove('show'); m.style.display = 'none'; }
  }
});

// Code preview toggle for template files
function toggleCodePreview(id, filename) {
  var el = document.getElementById(id);
  var btn = document.getElementById(id + '-btn');
  if (!el) return;
  if (el.style.display === 'none') {
    // Show — load code if not yet loaded
    var pre = document.getElementById(id + '-pre');
    if (pre && pre.textContent === _t('gl_loading') + '...') {
      fetch('/api/gallery/template/' + filename)
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.ok) { pre.textContent = data.content; }
          else { pre.textContent = _t('toast_error') + ': ' + (data.error || _t('toast_network_error')); }
        })
        .catch(function() { pre.textContent = _t('toast_network_error'); });
    }
    el.style.display = 'block';
    if (btn) { btn.textContent = '▾ Code'; btn.style.borderColor = 'var(--primary)'; btn.style.color = 'var(--primary)'; }
  } else {
    el.style.display = 'none';
    if (btn) { btn.textContent = '▸ Code'; btn.style.borderColor = 'var(--border-hover)'; btn.style.color = 'var(--ink-muted)'; }
  }
}

/* ── Live Editor (CodeMirror + HF Space API) ── */
var EDITOR_CM = null;
var EDITOR_ORIG_CODE = EDITOR_INITIAL_CODE;
var RENDER_API = (window.BRAIN_CONFIG && window.BRAIN_CONFIG.renderApi) || '/api/render';

function _loadCSS(href) {
  return new Promise(function(resolve) {
    if (document.querySelector('link[href="' + href + '"]')) { resolve(); return; }
    var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href;
    l.onload = resolve; l.onerror = resolve; document.head.appendChild(l);
  });
}
function _loadScript(src) {
  return new Promise(function(resolve) {
    if (document.querySelector('script[src="' + src + '"]')) { resolve(); return; }
    var s = document.createElement('script'); s.src = src;
    s.onload = resolve; s.onerror = resolve; document.head.appendChild(s);
  });
}

var _CM_BASE = 'https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.18/';

function loadCodeMirror() {
  return _loadCSS(_CM_BASE + 'codemirror.min.css')
    .then(function() { return _loadCSS(_CM_BASE + 'theme/material-darker.min.css'); })
    .then(function() { return _loadScript(_CM_BASE + 'codemirror.min.js'); })
    .then(function() { return _loadScript(_CM_BASE + 'mode/r/r.min.js'); });
}

function initLiveEditor() {
  var container = document.getElementById('editor-container');
  if (!container || typeof CodeMirror === 'undefined') return;
  EDITOR_CM = CodeMirror(container, {
    value: EDITOR_INITIAL_CODE,
    mode: 'r',
    theme: 'material-darker',
    lineNumbers: true,
    lineWrapping: true,
    indentUnit: 2,
    tabSize: 2,
    matchBrackets: true,
    styleActiveLine: true,
    viewportMargin: Infinity
  });
  var cmEl = container.querySelector('.CodeMirror');
  if (cmEl) { cmEl.style.height = 'auto'; cmEl.style.minHeight = '200px'; cmEl.style.maxHeight = '500px'; }
}

function runEditorCode() {
  if (!EDITOR_CM) return;
  var code = EDITOR_CM.getValue();
  var fmt = (document.getElementById('editor-format') || {}).value || 'png';
  var btn = document.getElementById('editor-run-btn');
  var img = document.getElementById('editor-preview-img');
  var ph = document.getElementById('editor-preview-placeholder');
  var err = document.getElementById('editor-preview-error');
  var status = document.getElementById('editor-preview-status');

  // UI: loading
  if (btn) { btn.textContent = '⏳ Running...'; btn.style.opacity = '0.6'; btn.disabled = true; }
  if (ph) ph.style.display = 'none';
  if (img) img.style.display = 'none';
  if (err) err.style.display = 'none';
  if (status) { status.style.display = 'none'; status.textContent = ''; }

  var start = Date.now();
  fetch(RENDER_API, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({script: code, format: fmt})
  }).then(function(r) {
    var elapsed = ((Date.now() - start) / 1000).toFixed(1);
    if (!r.ok) {
      return r.json().then(function(e) { throw new Error(e.detail || e.error || 'HTTP ' + r.status); });
    }
    if (fmt === 'pdf') {
      return r.blob().then(function(blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url; a.download = CHART_NAME + '_output.pdf'; a.click();
        if (status) { status.textContent = 'PDF downloaded (' + elapsed + 's)'; status.style.display = 'block'; status.style.color = 'var(--success)'; }
      });
    }
    return r.blob().then(function(blob) {
      var url = URL.createObjectURL(blob);
      if (img) { img.src = url; img.style.display = 'block'; }
      if (status) { status.textContent = 'Generated in ' + elapsed + 's'; status.style.display = 'block'; status.style.color = 'var(--success)'; }
    });
  }).catch(function(e) {
    if (err) { err.textContent = 'Error: ' + e.message; err.style.display = 'block'; }
  }).finally(function() {
    if (btn) { btn.textContent = '▶ Run'; btn.style.opacity = '1'; btn.disabled = false; }
  });
}

function resetEditorCode() {
  if (EDITOR_CM) EDITOR_CM.setValue(EDITOR_ORIG_CODE);
  var img = document.getElementById('editor-preview-img');
  var ph = document.getElementById('editor-preview-placeholder');
  var err = document.getElementById('editor-preview-error');
  var status = document.getElementById('editor-preview-status');
  if (img) img.style.display = 'none';
  if (err) err.style.display = 'none';
  if (status) status.style.display = 'none';
  if (ph) ph.style.display = 'block';
}

/* Ctrl+Enter / Cmd+Enter to run */
document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    var cm = document.querySelector('.CodeMirror');
    if (cm && cm.contains(document.activeElement)) { e.preventDefault(); runEditorCode(); }
  }
});

/* Init editor: load CodeMirror then create editor */
document.addEventListener('DOMContentLoaded', function() {
  loadCodeMirror().then(function() { initLiveEditor(); });
});
"""
    safe_name_json = _json.dumps(name)
    detail_js = f"var CHART_NAME = {safe_name_json};\nvar EDITOR_INITIAL_CODE = {_tpl_code_json};\n" + detail_js

    return _page(f"{title} — Gallery Detail", body, extra_js=detail_js, nav_active="gallery")


# ---------------------------------------------------------------------------
# Dashboard Page (unified: security + sub2api stats)
# ---------------------------------------------------------------------------

def _format_tokens(n: int) -> str:
    """Format token count: <1k as-is, 1k-999k as 'X.Xk', ≥1M as 'X.XM'."""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}k"
    return f"{n / 1_000_000:.1f}M"


def _format_cost(c: float) -> str:
    """Format cost: <0.01 → '$0.00', <100 → '$X.XX', else '$XXX'."""
    if c < 0.01:
        return "$0.00"
    if c < 100:
        return f"${c:.2f}"
    return f"${c:.0f}"


def home_page(*, node_counts: dict[str, int], chart_count: int, health_summary: dict, recent_nodes: list | None = None, do_status: dict | None = None, proxy_status: dict | None = None, proxy_traffic: list | None = None, sub2api: dict | None = None) -> str:
    """Render the home/landing page as a Notion-style personal dashboard."""
    total_nodes = sum(node_counts.values())
    canonized = node_counts.get("canonized", 0)
    draft = node_counts.get("draft", 0)
    refined = node_counts.get("refined", 0)
    verified = node_counts.get("verified", 0)
    deprecated = node_counts.get("deprecated", 0)

    # Stage badge colors
    stage_colors = {
        "draft": "#eab308",
        "refined": "#3b82f6",
        "verified": "#22c55e",
        "canonized": "#a78bfa",
        "deprecated": "#6b7280",
    }
    stage_labels = {
        "draft": _pt("stage_draft_short"),
        "refined": _pt("stage_refined_short"),
        "verified": _pt("stage_verified_short"),
        "canonized": _pt("stage_canonized_short"),
        "deprecated": _pt("stage_deprecated_short"),
    }

    # Build recent activity rows
    recent_items = ""
    if recent_nodes:
        for node in recent_nodes[:8]:
            stage = node.get("stage", "draft")
            color = stage_colors.get(stage, "#6b7280")
            label = stage_labels.get(stage, stage)
            summary = (node.get("summary") or _pt("dash_no_summary"))
            if len(summary) > 60:
                summary = summary[:57] + "..."
            created = node.get("created_at", "")
            nid = node.get("id", "")
            i18n_stage_key = f"stage_{stage}_short"
            recent_items += f'''<tr class="dash-activity-row">
  <td><span class="dash-stage-badge" style="background:{color}20;color:{color};border:1px solid {color}40" data-i18n="{_html.escape(i18n_stage_key)}">{_html.escape(label)}</span></td>
  <td class="dash-activity-summary">{_html.escape(summary)}</td>
  <td class="dash-activity-time" data-ts="{_html.escape(str(created))}">{_html.escape(str(created)[:10])}</td>
</tr>
'''
    else:
        recent_items = f'<tr><td colspan="3" class="dash-activity-empty" data-i18n="dash_no_activity">{_pt("dash_no_activity")}</td></tr>'

    # --- Build Sub2API hero cards and trend chart for home page ---
    _s2 = sub2api or {}
    _s2st = _s2.get("stats")
    _s2trend = _s2.get("trend") or []
    home_sub2api_cards = ""
    home_trend_data_js = "[]"
    home_need_chartjs = False
    if _s2st:
        home_need_chartjs = True
        _today_tokens = int(_s2st.get("today_tokens", 0))
        _today_requests = int(_s2st.get("today_requests", 0))
        _today_cost = float(_s2st.get("today_actual_cost", 0))
        _weekly_cost = sum(float(d.get("actual_cost", 0)) for d in _s2trend[-7:]) if _s2trend else _today_cost
        import json as _json_home
        _home_chart_data = []
        for d in _s2trend[-7:]:
            _home_chart_data.append({
                "date": d.get("date", "?")[5:],
                "tokens": int(d.get("total_tokens", 0)),
                "requests": int(d.get("total_requests", 0)),
                "cost": round(float(d.get("actual_cost", 0)), 2),
            })
        home_trend_data_js = _json_home.dumps(_home_chart_data)
        home_sub2api_cards = f"""  <!-- Sub2API Stats -->
  <section class="dash-section" style="animation-delay:.2s">
    <div class="dash-section-header">
      <h2 class="dash-section-title">⚡ Sub2API</h2>
    </div>
    <div class="dash-hero">
      <div class="dash-metric dash-metricPrimary dash-metricAccent">
        <div class="dash-num">{_format_tokens(_today_tokens)}</div>
        <div class="dash-label" data-i18n="dash_tokens">{_pt("dash_tokens")}</div>
      </div>
      <div class="dash-metric dash-metricSuccess">
        <div class="dash-num">{_today_requests}</div>
        <div class="dash-label" data-i18n="dash_requests">{_pt("dash_requests")}</div>
      </div>
      <div class="dash-metric{' dash-metricWarning' if _today_cost > 50 else ''}">
        <div class="dash-num">{_format_cost(_today_cost)}</div>
        <div class="dash-label" data-i18n="dash_cost">{_pt("dash_cost")}</div>
      </div>
      <div class="dash-metric">
        <div class="dash-num">{_format_cost(_weekly_cost)}</div>
        <div class="dash-label" data-i18n="dash_week">{_pt("dash_week")}</div>
      </div>
    </div>
    <div class="dash-trend-wrap" style="margin-top:var(--sp-md)">
      <div class="dash-trend-label">7-Day Token · Request · Cost Trend</div>
      <div class="dash-trend-chart-box"><canvas id="home-trend-chart"></canvas></div>
    </div>
  </section>
"""

    body = f"""

<div class="dash-wrap">

  <!-- Greeting -->
  <section class="dash-greeting" id="dash-greeting">
    <h1 id="dash-greeting-text" data-i18n="dash_greeting">你好，探索者</h1>
    <p class="dash-greeting-date" id="dash-greeting-date"></p>
  </section>

  <!-- Stat Cards — AxonHub style with icon watermarks -->
  <section class="dash-stat-grid">
    <div class="dash-stat-card" data-accent="primary">
      <div class="dash-stat-watermark">{_ICON_KNOWLEDGE}</div>
      <div class="dash-stat-value">{total_nodes}</div>
      <div class="dash-stat-label" data-i18n="dash_total">总节点</div>
    </div>
    <div class="dash-stat-card" data-accent="success">
      <div class="dash-stat-watermark">{_ICON_STATUS}</div>
      <div class="dash-stat-value" style="color:var(--primary)">{canonized}</div>
      <div class="dash-stat-label" data-i18n="dash_canonized">正典</div>
    </div>
    <div class="dash-stat-card" data-accent="info">
      <div class="dash-stat-watermark">{_ICON_GALLERY}</div>
      <div class="dash-stat-value" style="color:var(--info)">{refined}</div>
      <div class="dash-stat-label" data-i18n="dash_refined">精炼</div>
    </div>
    <div class="dash-stat-card" data-accent="warning">
      <div class="dash-stat-watermark">{_ICON_QUEUE}</div>
      <div class="dash-stat-value" style="color:var(--warning)">{draft}</div>
      <div class="dash-stat-label" data-i18n="dash_draft">草稿</div>
    </div>
  </section>

  <!-- Recent Activity — table style -->
  <section class="dash-section">
    <div class="dash-section-header">
      <h2 class="dash-section-title" data-i18n="dash_recent">📋 最近更新</h2>
      <a href="/knowledge" class="dash-section-link" data-i18n="dash_viewall">查看全部 →</a>
    </div>
    <div class="dash-table-wrap">
      <table class="dash-activity-table">
        <thead>
          <tr><th data-i18n="col_status">{_pt("col_status")}</th><th data-i18n="col_summary">{_pt("col_summary")}</th><th data-i18n="col_time">{_pt("col_time")}</th></tr>
        </thead>
        <tbody>
          {recent_items}
        </tbody>
      </table>
    </div>
  </section>

  <!-- Quick Access — horizontal icon cards -->
  <section class="dash-section">
    <div class="dash-section-header">
      <h2 class="dash-section-title" data-i18n="dash_shortcuts">⚡ 快捷入口</h2>
    </div>
    <div class="dash-quick-row">
      <a href="/knowledge" class="dash-quick-tile">
        <div class="dash-quick-tile-icon" style="background:var(--primary-muted);color:var(--primary)">{_ICON_KNOWLEDGE}</div>
        <span data-i18n="dash_knowledge">知识树</span>
      </a>
      <a href="/gallery" class="dash-quick-tile">
        <div class="dash-quick-tile-icon" style="background:var(--success-muted);color:var(--success)">{_ICON_GALLERY}</div>
        <span data-i18n="dash_gallery">绘图库</span>
      </a>
      <a href="/dashboard" class="dash-quick-tile">
        <div class="dash-quick-tile-icon" style="background:var(--info-muted);color:var(--info)">{_ICON_SHIELD}</div>
        <span data-i18n="dash_monitor">监控台</span>
      </a>
      <a href="/services" class="dash-quick-tile">
        <div class="dash-quick-tile-icon" style="background:rgba(251,191,36,.12);color:#fbbf24">{_ICON_SERVICES}</div>
        <span data-i18n="nav_services">服务</span>
      </a>
    </div>
  </section>



{home_sub2api_cards}

  <!-- Resource Monitor -->
  <section class="dash-section" style="animation-delay:.24s">
    <div class="dash-section-header">
      <h2 class="dash-section-title">📊 Resources</h2>
    </div>
    <div class="dash-resource-section" id="home-resource-section" style="margin:0">
      <div class="dash-res-card">
        <div class="dash-res-label">CPU</div>
        <div class="dash-res-value" id="home-res-cpu">—</div>
        <div class="dash-res-bar"><div class="dash-res-fill" id="home-res-cpu-bar" style="width:0;background:var(--primary)"></div></div>
      </div>
      <div class="dash-res-card">
        <div class="dash-res-label">Memory</div>
        <div class="dash-res-value" id="home-res-mem">—</div>
        <div class="dash-res-bar"><div class="dash-res-fill" id="home-res-mem-bar" style="width:0;background:var(--success)"></div></div>
        <div class="dash-res-sub" id="home-res-mem-sub"></div>
      </div>
      <div class="dash-res-card">
        <div class="dash-res-label">Disk</div>
        <div class="dash-res-value" id="home-res-disk">—</div>
        <div class="dash-res-bar"><div class="dash-res-fill" id="home-res-disk-bar" style="width:0;background:var(--warning)"></div></div>
        <div class="dash-res-sub" id="home-res-disk-sub"></div>
      </div>
      <div class="dash-res-card">
        <div class="dash-res-label">Load Avg</div>
        <div class="dash-res-value" id="home-res-load">—</div>
        <div class="dash-res-sub" id="home-res-load-sub"></div>
      </div>
    </div>
  </section>

  <!-- System Health Footer -->
  <footer class="dash-health-bar">
    <div class="dash-health-indicator">
      <span class="dash-health-dot" style="background:var(--success);box-shadow:0 0 8px rgba(52,211,153,.5)"></span>
      <span data-i18n="pf_status_run">正常运行</span>
    </div>
    <div class="dash-health-indicator">
      <span class="dash-health-dot" style="background:var(--success);box-shadow:0 0 8px rgba(52,211,153,.5)"></span>
      <span data-i18n="dash_auth_notice">联合登录</span>
    </div>
  </footer>

</div>

<style>
/* ---- AxonHub-style Dashboard ---- */
.dash-wrap {{
  max-width: 860px;
  margin: 0 auto;
  padding: var(--sp-lg) var(--sp-lg) var(--sp-xl);
  animation: pageEnter .4s var(--ease-out);
}}

/* Greeting */
.dash-greeting {{
  padding: var(--sp-xl) 0 var(--sp-lg);
}}
.dash-greeting h1 {{
  font-size: 28px;
  font-weight: 800;
  color: var(--ink);
  letter-spacing: -0.5px;
  margin: 0 0 4px;
}}
.dash-greeting-date {{
  font-size: 14px;
  color: var(--ink-muted);
  margin: 0;
}}

/* Stat Cards — AxonHub watermark style */
.dash-stat-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
  animation: staggerFade .3s var(--ease-out) .06s both;
}}
@media (max-width: 720px) {{
  .dash-stat-grid {{ grid-template-columns: repeat(2, 1fr); gap: var(--sp-sm); }}
}}
.dash-stat-card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: var(--sp-lg) var(--sp-md);
  position: relative;
  overflow: hidden;
  transition: all var(--duration) var(--ease-out);
  min-height: 100px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}}
.dash-stat-card:hover {{
  border-color: var(--border-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md), 0 0 0 1px var(--border-hover);
}}
.dash-stat-card[data-accent="primary"] {{ border-left: 3px solid var(--primary); }}
.dash-stat-card[data-accent="success"] {{ border-left: 3px solid var(--primary); }}
.dash-stat-card[data-accent="info"] {{ border-left: 3px solid var(--info); }}
.dash-stat-card[data-accent="warning"] {{ border-left: 3px solid var(--warning); }}
.dash-stat-watermark {{
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0.06;
  pointer-events: none;
}}
.dash-stat-watermark svg {{ width: 56px; height: 56px; }}
.dash-stat-value {{
  font-size: 2.2rem;
  font-weight: 800;
  line-height: 1;
  color: var(--ink);
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}}
.dash-stat-label {{
  font-size: .72rem;
  color: var(--ink-muted);
  text-transform: uppercase;
  letter-spacing: .08em;
  font-weight: 600;
  margin-top: 6px;
}}

/* Section headers */
.dash-section {{
  margin-bottom: var(--sp-lg);
  animation: staggerFade .3s var(--ease-out) .12s both;
}}
.dash-section-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-sm);
}}
.dash-section-title {{
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  margin: 0;
  letter-spacing: -0.01em;
}}
.dash-section-link {{
  font-size: .82rem;
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
  transition: color var(--duration);
}}
.dash-section-link:hover {{ color: var(--ink); }}

/* Activity Table — AxonHub style */
.dash-table-wrap {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
}}
.dash-activity-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: .88rem;
}}
.dash-activity-table thead {{
  background: var(--surface);
}}
.dash-activity-table th {{
  padding: 10px 14px;
  text-align: left;
  color: var(--ink-muted);
  font-size: .72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .06em;
  border-bottom: 1px solid var(--border);
}}
.dash-activity-table td {{
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}}
.dash-activity-table tbody tr:last-child td {{
  border-bottom: none;
}}
.dash-activity-table tbody tr {{
  transition: background var(--duration);
}}
.dash-activity-table tbody tr:hover {{
  background: var(--card-hover);
}}
.dash-stage-badge {{
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--r-pill);
  white-space: nowrap;
  display: inline-block;
}}
.dash-activity-summary {{
  color: var(--ink);
  max-width: 380px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.dash-activity-time {{
  font-size: .78rem;
  color: var(--ink-dim);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}}
.dash-activity-empty {{
  text-align: center;
  color: var(--ink-dim);
  padding: var(--sp-lg);
  font-size: .9rem;
}}

/* Quick Access — horizontal tile row */
.dash-quick-row {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-sm);
}}
@media (max-width: 720px) {{
  .dash-quick-row {{ grid-template-columns: 1fr 1fr; }}
}}
.dash-quick-tile {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px 12px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  text-decoration: none;
  color: var(--ink);
  font-size: .88rem;
  font-weight: 600;
  transition: all .2s var(--ease-out);
  text-align: center;
}}
.dash-quick-tile:hover {{
  border-color: var(--primary);
  transform: translateY(-2px) scale(1.02);
  box-shadow: var(--shadow-md), 0 0 0 1px var(--primary);
  color: var(--ink);
  text-decoration: none;
}}
.dash-quick-tile-icon {{
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r-md);
}}
.dash-quick-tile-icon svg {{ width: 22px; height: 22px; }}

/* Health bar footer */
.dash-health-bar {{
  display: flex;
  gap: var(--sp-xl);
  padding: var(--sp-md) 0;
  border-top: 1px solid var(--border);
  margin-top: var(--sp-md);
  animation: staggerFade .3s var(--ease-out) .2s both;
}}
.dash-health-indicator {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: .82rem;
  color: var(--ink-muted);
  font-weight: 500;
}}
.dash-health-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}}

/* Responsive */
@media (max-width: 640px) {{
  .dash-greeting h1 {{ font-size: 22px; }}
  .dash-stat-value {{ font-size: 1.6rem; }}
  .dash-stat-card {{ padding: var(--sp-md); min-height: 80px; }}
  .dash-activity-table {{ font-size: .82rem; }}
  .dash-activity-summary {{ max-width: 200px; }}
}}
</style>
"""
    _chartjs_tag = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js" crossorigin="anonymous"></script>' if home_need_chartjs else ''
    return _page("Hermes Brain", body, nav_active="home", extra_js=_chartjs_tag + '<script>' + """
(function(){
  /* Greeting: time-of-day + display_name from localStorage */
  var h = new Date().getHours();
  var greet = h < 12 ? _t('greeting_morning') : h < 18 ? _t('greeting_afternoon') : _t('greeting_evening');
  var name = localStorage.getItem('hermes_display_name') || _t('pf_explorer');
  var el = document.getElementById('dash-greeting-text');
  if(el) el.textContent = greet + _t('time_comma') + name;
  /* Date subtitle */
  var days = [_t('time_sun'),_t('time_mon'),_t('time_tue'),_t('time_wed'),_t('time_thu'),_t('time_fri'),_t('time_sat')];
  var months = [_t('time_jan'),_t('time_feb'),_t('time_mar'),_t('time_apr'),_t('time_may'),_t('time_jun'),_t('time_jul'),_t('time_aug'),_t('time_sep'),_t('time_oct'),_t('time_nov'),_t('time_dec')];
  var now = new Date();
  var dateStr = days[now.getDay()] + _t('time_comma') + months[now.getMonth()] + ' ' + now.getDate() + _t('time_day_suffix');
  var dateEl = document.getElementById('dash-greeting-date');
  if(dateEl) dateEl.textContent = dateStr;
  /* Relative time for activity rows */
  document.querySelectorAll('.dash-activity-time[data-ts]').forEach(function(el){
    var ts = el.getAttribute('data-ts');
    if(!ts) return;
    var d = new Date(ts);
    if(isNaN(d.getTime())) return;
    var diff = (Date.now() - d.getTime()) / 1000;
    var r;
    if(diff < 60) r = _t('time_just');
    else if(diff < 3600) r = Math.floor(diff/60) + _t('time_min_ago');
    else if(diff < 86400) r = Math.floor(diff/3600) + _t('time_hr_ago');
    else if(diff < 604800) r = Math.floor(diff/86400) + _t('time_day_ago');
    else r = (d.getMonth()+1) + '/' + d.getDate();
    el.textContent = r;
  });
  /* Resource monitor for home page */
  function _homeCheckResources() {
    fetch('/api/dashboard/resources').then(function(r){ return r.json(); }).then(function(d) {
      function barColor(pct) {
        if (pct > 85) return 'var(--danger)';
        if (pct > 65) return 'var(--warning)';
        return null;
      }
      var cpu = d.cpu_percent || 0;
      var cpuBar = document.getElementById('home-res-cpu-bar');
      var cpuVal = document.getElementById('home-res-cpu');
      if (cpuBar) { cpuBar.style.width = cpu + '%'; if (barColor(cpu)) cpuBar.style.background = barColor(cpu); }
      if (cpuVal) cpuVal.textContent = cpu + '%';
      var mem = d.mem_percent || 0;
      var memBar = document.getElementById('home-res-mem-bar');
      var memVal = document.getElementById('home-res-mem');
      var memSub = document.getElementById('home-res-mem-sub');
      if (memBar) { memBar.style.width = mem + '%'; if (barColor(mem)) memBar.style.background = barColor(mem); }
      if (memVal) memVal.textContent = mem + '%';
      if (memSub) memSub.textContent = (d.mem_used_gb || 0) + '/' + (d.mem_total_gb || 0) + ' GB';
      var disk = d.disk_percent || 0;
      var diskBar = document.getElementById('home-res-disk-bar');
      var diskVal = document.getElementById('home-res-disk');
      var diskSub = document.getElementById('home-res-disk-sub');
      if (diskBar) { diskBar.style.width = disk + '%'; if (barColor(disk)) diskBar.style.background = barColor(disk); }
      if (diskVal) diskVal.textContent = disk + '%';
      if (diskSub) diskSub.textContent = (d.disk_used_gb || 0) + '/' + (d.disk_total_gb || 0) + ' GB';
      var loadEl = document.getElementById('home-res-load');
      var loadSub = document.getElementById('home-res-load-sub');
      if (loadEl) loadEl.textContent = (d.load_1m || 0).toFixed(2);
      if (loadSub) loadSub.textContent = '5m: ' + (d.load_5m || 0).toFixed(2) + '  15m: ' + (d.load_15m || 0).toFixed(2);
    }).catch(function() {});
  }
  /* Home trend chart init */
  function _homeInitTrend() {
    var el = document.getElementById('home-trend-chart');
    if (!el || typeof Chart === 'undefined') return;
    var data = """ + home_trend_data_js + """;
    if (!data || data.length === 0) return;
    var _cs = getComputedStyle(document.documentElement);
    var _cPrimary = _cs.getPropertyValue('--primary').trim() || '#a78bfa';
    var _cSuccess = _cs.getPropertyValue('--success').trim() || '#34d399';
    var _cWarning = _cs.getPropertyValue('--warning').trim() || '#fbbf24';
    var _cInkMuted = _cs.getPropertyValue('--ink-muted').trim() || '#8b90a5';
    var _cInk = _cs.getPropertyValue('--ink').trim() || '#e2e4ed';
    var _cBg = _cs.getPropertyValue('--bg').trim() || '#1a1a2e';
    new Chart(el, {
      type: 'line',
      data: {
        labels: data.map(function(d){ return d.date; }),
        datasets: [{
          label: 'Tokens',
          data: data.map(function(d){ return d.tokens; }),
          borderColor: _cPrimary,
          backgroundColor: 'rgba(167,139,250,.12)',
          fill: true, tension: 0.35, pointRadius: 3, pointHoverRadius: 6,
          pointBackgroundColor: _cPrimary, borderWidth: 2, yAxisID: 'y'
        },{
          label: 'Requests',
          data: data.map(function(d){ return d.requests; }),
          borderColor: _cSuccess,
          backgroundColor: 'rgba(52,211,153,.08)',
          fill: true, tension: 0.35, pointRadius: 2, pointHoverRadius: 5,
          pointBackgroundColor: _cSuccess, borderWidth: 1.5, yAxisID: 'y1'
        },{
          label: 'Cost ($)',
          data: data.map(function(d){ return d.cost; }),
          borderColor: _cWarning,
          backgroundColor: 'rgba(251,191,36,.10)',
          fill: false, tension: 0.35, pointRadius: 3, pointHoverRadius: 6,
          pointBackgroundColor: _cWarning, borderWidth: 2, borderDash: [4, 3], yAxisID: 'y2'
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: true, position: 'top', labels: { boxWidth: 12, padding: 12 } },
          tooltip: {
            backgroundColor: _cBg, titleColor: _cInk, bodyColor: _cInkMuted, borderColor: _cPrimary, borderWidth: 1, padding: 10, cornerRadius: 8,
            callbacks: {
              label: function(ctx) {
                if (ctx.dataset.label === 'Cost ($)') return 'Cost: $' + ctx.parsed.y.toFixed(2);
                return ctx.dataset.label + ': ' + ctx.formattedValue;
              }
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10 } } },
          y: { type: 'linear', position: 'left', grid: { color: 'rgba(255,255,255,.04)' }, ticks: { callback: function(v){ return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v; } } },
          y1: { type: 'linear', position: 'right', min: 0, grid: { display: false }, ticks: { callback: function(v){ return v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v; } } },
          y2: { type: 'linear', position: 'right', min: 0, grid: { display: false }, ticks: { callback: function(v){ return '$'+v.toFixed(0); } } }
        }
      }
    });
  }
  _homeCheckResources();
  _homeInitTrend();
  /* Auto-refresh resources every 30s */
  setInterval(function() { _homeCheckResources(); }, 30000);
})();
</script>""")


def dashboard_page(
    *,
    do_status: dict,
    proxy_status: dict,
    proxy_traffic: list[dict],
    sub2api: dict,
) -> str:
    """Render unified dashboard: health overview cards + security kanban + sub2api stats."""
    st = sub2api.get("stats") or {}
    trend = sub2api.get("trend") or []
    groups = sub2api.get("groups") or []
    do = do_status
    pr = proxy_status

    # --- Identify worker groups (exclude admin/management accounts) ---
    # Admin accounts are on platforms other than "openai" (e.g. antigravity).
    # Only openai platform accounts are real upstream workers serving API requests.
    worker_groups = [g for g in groups if g.get("platform") == "openai"]
    worker_total = sum(g.get("account_count", 0) for g in worker_groups)
    worker_ratelimit = sum(g.get("rate_limited_account_count", 0) or 0 for g in worker_groups)
    worker_active = sum(g.get("active_account_count", 0) for g in worker_groups)
    admin_accts = int(st.get("total_accounts", 0)) - worker_total

    # --- Sub2API stat cards ---
    today_tokens = int(st.get("today_tokens", 0))
    today_requests = int(st.get("today_requests", 0))
    today_cost = float(st.get("today_actual_cost", 0))
    # Weekly cost = sum of last 7 days' actual_cost from trend data
    weekly_cost = sum(float(d.get("actual_cost", 0)) for d in trend[-7:]) if trend else today_cost
    # Use worker-only account counts for monitored pool
    if worker_total > 0:
        total_accts = worker_total
        ratelimit_accts = worker_ratelimit
    else:
        total_accts = int(st.get("total_accounts", 0))
        ratelimit_accts = int(st.get("ratelimit_accounts", 0))
    error_accts = int(st.get("error_accounts", 0))
    normal_accts = total_accts - ratelimit_accts - error_accts
    active_keys = int(st.get("active_api_keys", 0))
    # Percentage for donut legend
    normal_pct = round(normal_accts / total_accts * 100) if total_accts > 0 else 0
    rl_pct = round(ratelimit_accts / total_accts * 100) if total_accts > 0 else 0

    # Account health badge
    if error_accts == 0 and ratelimit_accts == 0:
        acct_status = ("✅ Healthy", "var(--success)")
    elif error_accts > 0:
        acct_status = (f"⚠️ {error_accts} errors", "var(--danger)")
    else:
        acct_status = (f"🔶 {ratelimit_accts} limited", "var(--warning)")

    # --- Security data ---
    f2b_banned = do.get("f2b_banned", [])
    ssh_port = do.get("ssh_port", "22")
    ufw_rules = do.get("ufw_rules", [])
    top_attackers = do.get("top_attackers", [])
    uptime = do.get("uptime", "?")
    sysctl = do.get("sysctl", {})

    pr_f2b_banned = pr.get("f2b_banned", [])
    pr_ssh_port = pr.get("ssh_port", "22")
    pr_ufw_rules = pr.get("ufw_rules", [])
    pr_uptime = pr.get("uptime", "?")
    pr_sysctl = pr.get("sysctl", {})

    # Attacker rows
    attacker_rows = ""
    max_cnt = max((a.get("count", 0) for a in top_attackers), default=1) or 1
    for a in top_attackers[:8]:
        ip = _html.escape(a.get("ip", "?"))
        cnt = a.get("count", 0)
        bar_w = min(cnt / max_cnt * 100, 100)
        bar_color = "var(--success)" if cnt / max_cnt < 0.3 else "var(--warning)" if cnt / max_cnt < 0.7 else "var(--danger)"
        attacker_rows += f"""<div class="sec-bar-row">
  <span class="sec-ip">{ip}</span>
  <div class="sec-bar-bg"><div class="sec-bar-fill" style="width:{bar_w:.0f}%;background:{bar_color}"></div></div>
  <span class="sec-cnt">{cnt}</span>
</div>"""

    def _ufw_rows(rules):
        rows = ""
        for r in rules:
            action = _html.escape(r.get("action", "?"))
            to = _html.escape(r.get("to", "?"))
            comment = _html.escape(r.get("comment", ""))
            action_cls = "allow" if action == "ALLOW" else "deny" if action in ("REJECT", "DENY") else "other"
            rows += f"""<div class="sec-ufw-row">
  <span class="sec-ufw-action {action_cls}">{action}</span>
  <span class="sec-ufw-to">{to}</span>
  <span class="sec-ufw-comment">{comment}</span>
</div>"""
        return rows

    do_ufw_rows = _ufw_rows(ufw_rules)
    pr_ufw_rows = _ufw_rows(pr_ufw_rules)

    # Proxy traffic
    traffic_rows = ""
    for t in proxy_traffic:
        name = _html.escape(t.get("name", "?"))
        proto = _html.escape(t.get("proto", "?"))
        port = t.get("port", 0)
        up_mb = t.get("up", 0) / 1048576
        down_mb = t.get("down", 0) / 1048576
        enable = t.get("enable", False)
        dot_cls = "dot-green" if enable else "dot-red"
        clients = t.get("clients", [])
        client_rows = ""
        for c in clients:
            c_email = _html.escape(c.get("email", "?"))
            c_up = c.get("up", 0) / 1048576
            c_down = c.get("down", 0) / 1048576
            c_enable = c.get("enable", False)
            c_dot = "dot-green" if c_enable else "dot-red"
            client_rows += f"""<div class="sec-client-row">
    <span class="dot {c_dot}"></span>
    <span class="sec-client-name">{c_email}</span>
    <span class="sec-client-traffic">{c_up:.1f}↑ {c_down:.1f}↓ MB</span>
  </div>"""
        traffic_rows += f"""<div class="sec-inbound-card">
  <div class="sec-inbound-header">
    <span class="dot {dot_cls}"></span>
    <span class="sec-inbound-name">{name}</span>
    <span class="sec-inbound-meta">{proto} :{port}</span>
    <span class="sec-inbound-traffic">{up_mb:.1f}↑ {down_mb:.1f}↓ MB</span>
  </div>
  <div class="sec-inbound-clients">{client_rows}</div>
</div>"""

    f2b_badge = f'<span class="sec-badge sec-badge-red">{len(f2b_banned)} banned</span>'
    pr_badge = f'<span class="sec-badge sec-badge-red">{len(pr_f2b_banned)} banned</span>'

    def _sysctl_items(sc):
        syn = sc.get("syncookies", False)
        redir = not sc.get("accept_redirects", True)
        fwd = not sc.get("ip_forward", True)
        return [("Syncookies", "✅" if syn else "❌", syn), ("ICMP Redir", "✅" if redir else "❌", redir), ("IP Forward", "✅" if fwd else "⚠️", fwd)]

    do_sysctl = _sysctl_items(sysctl)
    pr_sysctl_items = _sysctl_items(pr_sysctl)

    def _sysctl_grid(items):
        rows = ""
        for label, icon, ok in items:
            val_cls = "sec-sysctl-value" + ("" if ok else " style='color:var(--danger)'")
            rows += f'<div class="sec-sysctl-item"><span class="sec-sysctl-label">{label}</span><span {val_cls}>{icon}</span></div>'
        return rows

    # --- Build trend chart data (Chart.js area chart) ---
    trend_data_js = "[]"
    if trend:
        import json as _json_mod
        chart_data = []
        for d in trend[-7:]:
            chart_data.append({
                "date": d.get("date", "?")[5:],
                "tokens": int(d.get("total_tokens", 0)),
                "requests": int(d.get("total_requests", 0)),
                "cost": round(float(d.get("actual_cost", 0)), 2),
            })
        trend_data_js = _json_mod.dumps(chart_data)
    trend_chart = f"""<div class="dash-trend-wrap">
  <div class="dash-trend-label">7-Day Token · Request · Cost Trend</div>
  <div class="dash-trend-chart-box"><canvas id="dash-trend-chart"></canvas></div>
</div>"""

    # --- Hero metrics (top strip) ---
    sub2api_available = st is not None
    if sub2api_available:
        hero_cards = f"""<div class="dash-hero">
  <div class="dash-metric dash-metricPrimary dash-metricAccent">
    <div class="dash-num">{_format_tokens(today_tokens)}</div>
    <div class="dash-label" data-i18n="dash_tokens">今日 Tokens</div>
  </div>
  <div class="dash-metric dash-metricSuccess">
    <div class="dash-num">{today_requests}</div>
    <div class="dash-label" data-i18n="dash_requests">今日请求数</div>
  </div>
  <div class="dash-metric{' dash-metricWarning' if today_cost > 50 else ''}">
    <div class="dash-num">{_format_cost(today_cost)}</div>
    <div class="dash-label" data-i18n="dash_cost">今日费用</div>
  </div>
  <div class="dash-metric">
    <div class="dash-num">{_format_cost(weekly_cost)}</div>
    <div class="dash-label" data-i18n="dash_week">本周费用</div>
  </div>
</div>"""
    else:
        hero_cards = ""

    # --- API Gateway detail section ---
    if sub2api_available:
        # Compute health color class
        if error_accts > 0:
            health_cls = "dash-metricDanger"
        elif ratelimit_accts > 0:
            health_cls = "dash-metricWarning"
        else:
            health_cls = "dash-metricSuccess"
        api_section = f"""<div class="dash-api-section">
  <div class="dash-api-header">
    <h2>⚡ API Gateway <span style="font-size:.72rem;color:var(--ink-dim);font-weight:400;margin-left:4px">{normal_accts}/{total_accts} workers</span>{f'<span style="font-size:.68rem;color:var(--ink-dim);margin-left:6px">({admin_accts} admin excl.)</span>' if admin_accts > 0 else ''}</h2>
    <div class="sec-api-status">
      <span class="dot {'dot-green' if error_accts == 0 and ratelimit_accts == 0 else 'dot-amber' if ratelimit_accts > 0 else 'dot-red'}"></span>
      <span style="color:{acct_status[1]}">{acct_status[0].replace('✅ ','').replace('⚠️ ','').replace('🔶 ','')}</span>
      <span style="color:var(--ink-dim)">·</span>
      <span style="color:var(--ink-muted)">{active_keys} keys</span>
    </div>
  </div>
  <div class="dash-api-grid">
    <div class="dash-api-card">
      <div class="dash-num" style="color:var(--primary)">{_format_tokens(int(st.get('total_tokens', 0)))}</div>
      <div class="dash-label" data-i18n="dash_total_tokens">累计 Tokens</div>
    </div>
    <div class="dash-api-card">
      <div class="dash-num" style="color:var(--ink)">{int(st.get('total_requests', 0))}</div>
      <div class="dash-label" data-i18n="dash_total_req">累计请求数</div>
    </div>
    <div class="dash-api-card">
      <div class="dash-num" style="color:var(--ink-muted)">{int(st.get('total_users', 0))}</div>
      <div class="dash-label" data-i18n="dash_users">用户数</div>
    </div>
    <div class="dash-api-card">
      <div class="dash-num" style="color:var(--ink-dim)">{int(st.get('rpm', 0))}</div>
      <div class="dash-label" data-i18n="dash_rpm">RPM(请求/分)</div>
    </div>
  </div>
  {trend_chart}
  <div class="dash-charts-row">
    <div class="dash-trend-wrap">
      <div class="dash-trend-label">7-Day Cost Breakdown</div>
      <div class="dash-trend-chart-box"><canvas id="dash-cost-bar"></canvas></div>
    </div>
    <div class="dash-donut-wrap" style="flex-direction:column;align-items:center;gap:var(--sp-sm)">
      <div class="dash-trend-label" style="margin-bottom:0">Worker Status</div>
      <div class="dash-donut-canvas-wrap"><canvas id="dash-acct-donut" width="120" height="120"></canvas></div>
      <div class="dash-donut-legend">
        <div class="dash-donut-legend-item"><span class="dash-donut-legend-dot" style="background:var(--success)"></span><span>Normal</span><span class="dash-donut-legend-value">{normal_accts} <span style="color:var(--ink-dim);font-weight:400;font-size:.72rem">({normal_pct}%)</span></span></div>
        <div class="dash-donut-legend-item"><span class="dash-donut-legend-dot" style="background:var(--warning)"></span><span>Rate-limited</span><span class="dash-donut-legend-value">{ratelimit_accts} <span style="color:var(--ink-dim);font-weight:400;font-size:.72rem">({rl_pct}%)</span></span></div>
        <div class="dash-donut-legend-item"><span class="dash-donut-legend-dot" style="background:var(--danger)"></span><span>Errors</span><span class="dash-donut-legend-value">{error_accts}</span></div>
      </div>
    </div>
  </div>
</div>"""
    else:
        api_section = """<div class="dash-api-section">
  <div class="dash-api-header"><h2>⚡ API Gateway</h2></div>
  <span class="sec-empty">Sub2API data unavailable</span>
</div>"""

    body = f"""
<div class="sec-header">
  <h1>Dashboard</h1>
  <span class="sec-refresh" id="refresh-indicator">Live</span>
  <button class="sec-pause-btn" id="pause-btn" onclick="toggleRefresh()" title="Pause auto-refresh">⏸</button>
  <span class="refresh-info" id="last-updated"></span>
</div>

{hero_cards}

<div class="dash-uptime-section">
  <div class="dash-uptime-card">
    <div class="dash-uptime-header">
      <h3>📊 <span data-i18n="dash_monitor_title_inner">服务监控</span></h3>
      <a href="#" target="_blank" rel="noopener" class="dash-uptime-link">打开 Uptime Kuma ↗</a>
    </div>
    <div class="dash-uptime-grid">
      <a href="#" target="_blank" rel="noopener" class="dash-uptime-item">
        <div class="dash-uptime-icon">🟢</div>
        <div class="dash-uptime-info">
          <div class="dash-uptime-name">Uptime Kuma</div>
          <div class="dash-uptime-desc">全栈服务状态监控 · 历史可用性数据</div>
        </div>
        <div class="dash-uptime-arrow">→</div>
      </a>
    </div>
  </div>
  <div class="dash-uptime-note">
    <span class="note-icon">🔗</span>
    <span><strong data-i18n="dash_auth_notice">联合登录</strong> — <span data-i18n="dash_auth_notice2">与本系统共享凭据</span></span>
  </div>
</div>

<div class="dash-resource-section" id="resource-section">
  <div class="dash-res-card">
    <div class="dash-res-label">CPU</div>
    <div class="dash-res-value" id="res-cpu">—</div>
    <div class="dash-res-bar"><div class="dash-res-fill" id="res-cpu-bar" style="width:0;background:var(--primary)"></div></div>
  </div>
  <div class="dash-res-card">
    <div class="dash-res-label">Memory</div>
    <div class="dash-res-value" id="res-mem">—</div>
    <div class="dash-res-bar"><div class="dash-res-fill" id="res-mem-bar" style="width:0;background:var(--success)"></div></div>
    <div class="dash-res-sub" id="res-mem-sub"></div>
  </div>
  <div class="dash-res-card">
    <div class="dash-res-label">Disk</div>
    <div class="dash-res-value" id="res-disk">—</div>
    <div class="dash-res-bar"><div class="dash-res-fill" id="res-disk-bar" style="width:0;background:var(--warning)"></div></div>
    <div class="dash-res-sub" id="res-disk-sub"></div>
  </div>
  <div class="dash-res-card">
    <div class="dash-res-label">Load Avg</div>
    <div class="dash-res-value" id="res-load">—</div>
    <div class="dash-res-sub" id="res-load-sub"></div>
  </div>
</div>

{api_section}

<div class="sec-kanban">

  <div class="sec-col">
    <div class="sec-col-header">🏠 DO VPS <span class="sec-badge">:{ssh_port}</span> {f2b_badge}</div>
    <div class="sec-section">
      <div class="sec-section-title">Overview</div>
      <div class="sec-card">
        <div class="sec-stat-row"><span class="stat-label">Uptime</span><span class="stat-value">{_html.escape(uptime)}</span></div>
      </div>
      <div class="sec-sysctl-grid">{_sysctl_grid(do_sysctl)}</div>
    </div>
    <div class="sec-section">
      <div class="sec-section-title">Top Attackers</div>
      <div class="sec-card">{attacker_rows if attacker_rows else '<span class="sec-empty">No recent attackers</span>'}</div>
    </div>
    <div class="sec-section">
      <div class="sec-section-title">Firewall Rules ({len(ufw_rules)})</div>
      <div class="sec-card">{do_ufw_rows if do_ufw_rows else '<span class="sec-empty">No rules</span>'}</div>
    </div>
  </div>

  <div class="sec-col">
    <div class="sec-col-header">🌐 Proxy VPS <span class="sec-badge">:{pr_ssh_port}</span> {pr_badge}</div>
    <div class="sec-section">
      <div class="sec-section-title">Overview</div>
      <div class="sec-card">
        <div class="sec-stat-row"><span class="stat-label">Uptime</span><span class="stat-value">{_html.escape(pr_uptime)}</span></div>
      </div>
      <div class="sec-sysctl-grid">{_sysctl_grid(pr_sysctl_items)}</div>
    </div>
    <div class="sec-section">
      <div class="sec-section-title">Proxy Traffic</div>
      {traffic_rows if traffic_rows else '<div class="sec-card"><span class="sec-empty">No inbound data</span></div>'}
    </div>
    <div class="sec-section">
      <div class="sec-section-title">Firewall Rules ({len(pr_ufw_rules)})</div>
      <div class="sec-card">{pr_ufw_rows if pr_ufw_rows else '<span class="sec-empty">No rules</span>'}</div>
    </div>
  </div>

</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js" crossorigin="anonymous"></script>
<script>
var _secTimer = null;
var _secPaused = false;
var _lastDashData = null;
var _trendChart = null;
var _acctDonut = null;

// --- Chart.js theme ---
var _cs = getComputedStyle(document.documentElement);
var _cPrimary = _cs.getPropertyValue('--primary').trim() || '#a78bfa';
var _cSuccess = _cs.getPropertyValue('--success').trim() || '#34d399';
var _cInkMuted = _cs.getPropertyValue('--ink-muted').trim() || '#8b90a5';
var _cInk = _cs.getPropertyValue('--ink').trim() || '#e2e4ed';
var _cBg = _cs.getPropertyValue('--bg').trim() || '#1a1a2e';
Chart.defaults.color = _cInkMuted;
Chart.defaults.borderColor = 'rgba(255,255,255,.06)';
Chart.defaults.font.family = '-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif';
Chart.defaults.font.size = 11;

function _initTrendChart() {{
  var el = document.getElementById('dash-trend-chart');
  if (!el) return;
  var data = {trend_data_js};
  if (!data || data.length === 0) return;
  var _cWarning = _cs.getPropertyValue('--warning').trim() || '#fbbf24';
  _trendChart = new Chart(el, {{
    type: 'line',
    data: {{
      labels: data.map(function(d){{ return d.date; }}),
      datasets: [{{
        label: 'Tokens',
        data: data.map(function(d){{ return d.tokens; }}),
        borderColor: _cPrimary,
        backgroundColor: 'rgba(167,139,250,.12)',
        fill: true,
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: _cPrimary,
        borderWidth: 2,
        yAxisID: 'y'
      }},{{
        label: 'Requests',
        data: data.map(function(d){{ return d.requests; }}),
        borderColor: _cSuccess,
        backgroundColor: 'rgba(52,211,153,.08)',
        fill: true,
        tension: 0.35,
        pointRadius: 2,
        pointHoverRadius: 5,
        pointBackgroundColor: _cSuccess,
        borderWidth: 1.5,
        yAxisID: 'y1'
      }},{{
        label: 'Cost ($)',
        data: data.map(function(d){{ return d.cost; }}),
        borderColor: _cWarning,
        backgroundColor: 'rgba(251,191,36,.10)',
        fill: false,
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: _cWarning,
        borderWidth: 2,
        borderDash: [4, 3],
        yAxisID: 'y2'
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: true, position: 'top', labels: {{ boxWidth: 12, padding: 12 }} }},
        tooltip: {{
          backgroundColor: _cBg, titleColor: _cInk, bodyColor: _cInkMuted, borderColor: _cPrimary, borderWidth: 1, padding: 10, cornerRadius: 8,
          callbacks: {{
            label: function(ctx) {{
              if (ctx.dataset.label === 'Cost ($)') return 'Cost: $' + ctx.parsed.y.toFixed(2);
              return ctx.dataset.label + ': ' + ctx.formattedValue;
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }},
        y: {{ type: 'linear', position: 'left', grid: {{ color: 'rgba(255,255,255,.04)' }}, ticks: {{ callback: function(v){{ return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v; }} }} }},
        y1: {{ type: 'linear', position: 'right', min: 0, grid: {{ display: false }}, ticks: {{ callback: function(v){{ return v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v; }} }} }},
        y2: {{ type: 'linear', position: 'right', min: 0, grid: {{ display: false }}, ticks: {{ callback: function(v){{ return '$'+v.toFixed(0); }} }} }}
      }}
    }}
  }});
}}

function _initAcctDonut() {{
  var el = document.getElementById('dash-acct-donut');
  if (!el) return;
  var n = {normal_accts}, r = {ratelimit_accts}, e = {error_accts};
  if (n+r+e === 0) return;
  _acctDonut = new Chart(el, {{
    type: 'doughnut',
    data: {{
      labels: ['Normal', 'Rate-limited', 'Errors'],
      datasets: [{{ data: [n, r, e], backgroundColor: [_cSuccess, _cs.getPropertyValue('--warning').trim() || '#fbbf24', _cs.getPropertyValue('--danger').trim() || '#f87171'], borderWidth: 0, hoverOffset: 4 }}]
    }},
    options: {{
      responsive: false,
      cutout: '68%',
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ backgroundColor: _cBg, bodyColor: _cInk, borderColor: _cPrimary, borderWidth: 1, cornerRadius: 8 }}
      }}
    }}
  }});
}}

function _initCostBar() {{
  var el = document.getElementById('dash-cost-bar');
  if (!el) return;
  var data = {trend_data_js};
  if (!data || data.length === 0) return;
  var _cWarning = _cs.getPropertyValue('--warning').trim() || '#fbbf24';
  var _cDanger = _cs.getPropertyValue('--danger').trim() || '#f87171';
  var avgCost = data.reduce(function(s,d){{ return s + d.cost; }}, 0) / data.length;
  new Chart(el, {{
    type: 'bar',
    data: {{
      labels: data.map(function(d){{ return d.date; }}),
      datasets: [{{
        label: 'Daily Cost',
        data: data.map(function(d){{ return d.cost; }}),
        backgroundColor: data.map(function(d){{ return d.cost > avgCost * 1.5 ? _cDanger : d.cost > avgCost ? _cWarning : _cPrimary; }}),
        borderRadius: 4,
        maxBarThickness: 32
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: _cBg, titleColor: _cInk, bodyColor: _cInkMuted, borderColor: _cPrimary, borderWidth: 1, cornerRadius: 8,
          callbacks: {{ label: function(ctx){{ return 'Cost: $' + ctx.parsed.y.toFixed(2); }} }}
        }}
      }},
      scales: {{
        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }},
        y: {{ min: 0, grid: {{ color: 'rgba(255,255,255,.04)' }}, ticks: {{ callback: function(v){{ return '$' + v.toFixed(0); }} }} }}
      }}
    }}
  }});
}}

function _checkResources() {{
  fetch('/api/dashboard/resources').then(function(r){{ return r.json(); }}).then(function(d) {{
    function barColor(pct) {{
      if (pct > 85) return 'var(--danger)';
      if (pct > 65) return 'var(--warning)';
      return null;
    }}
    var cpu = d.cpu_percent || 0;
    var cpuBar = document.getElementById('res-cpu-bar');
    var cpuVal = document.getElementById('res-cpu');
    if (cpuBar) {{ cpuBar.style.width = cpu + '%'; if (barColor(cpu)) cpuBar.style.background = barColor(cpu); }}
    if (cpuVal) cpuVal.textContent = cpu + '%';

    var mem = d.mem_percent || 0;
    var memBar = document.getElementById('res-mem-bar');
    var memVal = document.getElementById('res-mem');
    var memSub = document.getElementById('res-mem-sub');
    if (memBar) {{ memBar.style.width = mem + '%'; if (barColor(mem)) memBar.style.background = barColor(mem); }}
    if (memVal) memVal.textContent = mem + '%';
    if (memSub) memSub.textContent = (d.mem_used_gb || 0) + '/' + (d.mem_total_gb || 0) + ' GB';

    var disk = d.disk_percent || 0;
    var diskBar = document.getElementById('res-disk-bar');
    var diskVal = document.getElementById('res-disk');
    var diskSub = document.getElementById('res-disk-sub');
    if (diskBar) {{ diskBar.style.width = disk + '%'; if (barColor(disk)) diskBar.style.background = barColor(disk); }}
    if (diskVal) diskVal.textContent = disk + '%';
    if (diskSub) diskSub.textContent = (d.disk_used_gb || 0) + '/' + (d.disk_total_gb || 0) + ' GB';

    var loadEl = document.getElementById('res-load');
    var loadSub = document.getElementById('res-load-sub');
    if (loadEl) loadEl.textContent = (d.load_1m || 0).toFixed(2);
    if (loadSub) loadSub.textContent = '5m: ' + (d.load_5m || 0).toFixed(2) + '  15m: ' + (d.load_15m || 0).toFixed(2);
  }}).catch(function() {{}});
}}

function toggleRefresh() {{
  if (_secPaused) {{
    _secPaused = false;
    document.getElementById('refresh-indicator').textContent = 'Live';
    document.getElementById('pause-btn').textContent = '⏸';
    scheduleRefresh();
  }} else {{
    _secPaused = true;
    document.getElementById('refresh-indicator').textContent = '⏸ Paused';
    document.getElementById('pause-btn').textContent = '▶';
    if (_secTimer) clearTimeout(_secTimer);
  }}
}}
function checkRefresh() {{
  fetch('/api/dashboard/data').then(function(r){{ return r.json(); }}).then(function(data) {{
    var sig = JSON.stringify(data);
    // Update "last updated" timestamp
    var now = new Date();
    var ts = now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0')+' '+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0')+':'+String(now.getSeconds()).padStart(2,'0');
    document.getElementById('last-updated').textContent = 'Updated ' + ts;
    if (_lastDashData && _lastDashData !== sig) {{
      location.reload();
    }} else {{
      _lastDashData = sig;
      scheduleRefresh();
    }}
  }}).catch(function() {{ scheduleRefresh(); }});
}}
function scheduleRefresh() {{
  if (!_secPaused) _secTimer = setTimeout(checkRefresh, 30000);
}}
// Init charts and resources
_initTrendChart();
_initAcctDonut();
_initCostBar();
_checkResources();
checkRefresh();
</script>"""

    return _page("Dashboard", body, nav_active="home")


# ---------------------------------------------------------------------------
# Security Monitoring Page (redirects to /dashboard)
# ---------------------------------------------------------------------------

def security_page(
    *,
    do_status: dict,
    proxy_status: dict,
    proxy_traffic: list[dict],
) -> str:
    """Render security monitoring kanban."""
    # DO status
    do = do_status
    f2b_banned = do.get("f2b_banned", [])
    ssh_port = do.get("ssh_port", "22")
    ufw_rules = do.get("ufw_rules", [])
    top_attackers = do.get("top_attackers", [])
    uptime = do.get("uptime", "?")
    sysctl = do.get("sysctl", {})

    # Proxy status
    pr = proxy_status
    pr_f2b_banned = pr.get("f2b_banned", [])
    pr_ssh_port = pr.get("ssh_port", "22")
    pr_ufw_rules = pr.get("ufw_rules", [])
    pr_uptime = pr.get("uptime", "?")
    pr_sysctl = pr.get("sysctl", {})

    # Build attacker rows
    attacker_rows = ""
    max_cnt = max((a.get("count", 0) for a in top_attackers), default=1) or 1
    for a in top_attackers[:8]:
        ip = _html.escape(a.get("ip", "?"))
        cnt = a.get("count", 0)
        bar_w = min(cnt / max_cnt * 100, 100)
        bar_color = "var(--success)" if cnt / max_cnt < 0.3 else "var(--warning)" if cnt / max_cnt < 0.7 else "var(--danger)"
        attacker_rows += f"""<div class="sec-bar-row">
  <span class="sec-ip">{ip}</span>
  <div class="sec-bar-bg"><div class="sec-bar-fill" style="width:{bar_w:.0f}%;background:{bar_color}"></div></div>
  <span class="sec-cnt">{cnt}</span>
</div>"""

    # Build UFW rule rows for a given server
    def _ufw_rows(rules):
        rows = ""
        for r in rules:
            action = _html.escape(r.get("action", "?"))
            to = _html.escape(r.get("to", "?"))
            comment = _html.escape(r.get("comment", ""))
            action_cls = "allow" if action == "ALLOW" else "deny" if action in ("REJECT", "DENY") else "other"
            rows += f"""<div class="sec-ufw-row">
  <span class="sec-ufw-action {action_cls}">{action}</span>
  <span class="sec-ufw-to">{to}</span>
  <span class="sec-ufw-comment">{comment}</span>
</div>"""
        return rows

    do_ufw_rows = _ufw_rows(ufw_rules)
    pr_ufw_rows = _ufw_rows(pr_ufw_rules)

    # Build proxy traffic rows
    traffic_rows = ""
    for t in proxy_traffic:
        name = _html.escape(t.get("name", "?"))
        proto = _html.escape(t.get("proto", "?"))
        port = t.get("port", 0)
        up_mb = t.get("up", 0) / 1048576
        down_mb = t.get("down", 0) / 1048576
        enable = t.get("enable", False)
        dot_cls = "dot-green" if enable else "dot-red"
        clients = t.get("clients", [])
        client_rows = ""
        for c in clients:
            c_email = _html.escape(c.get("email", "?"))
            c_up = c.get("up", 0) / 1048576
            c_down = c.get("down", 0) / 1048576
            c_enable = c.get("enable", False)
            c_dot = "dot-green" if c_enable else "dot-red"
            client_rows += f"""<div class="sec-client-row">
    <span class="dot {c_dot}"></span>
    <span class="sec-client-name">{c_email}</span>
    <span class="sec-client-traffic">{c_up:.1f}↑ {c_down:.1f}↓ MB</span>
  </div>"""
        traffic_rows += f"""<div class="sec-inbound-card">
  <div class="sec-inbound-header">
    <span class="dot {dot_cls}"></span>
    <span class="sec-inbound-name">{name}</span>
    <span class="sec-inbound-meta">{proto} :{port}</span>
    <span class="sec-inbound-traffic">{up_mb:.1f}↑ {down_mb:.1f}↓ MB</span>
  </div>
  <div class="sec-inbound-clients">{client_rows}</div>
</div>"""

    # Banned IPs badges
    f2b_badge = f'<span class="sec-badge sec-badge-red" title="Banned IPs">{len(f2b_banned)} banned</span>'
    pr_badge = f'<span class="sec-badge sec-badge-red" title="Banned IPs">{len(pr_f2b_banned)} banned</span>'

    # Sysctl items for grid layout
    def _sysctl_items(sc):
        syn = sc.get("syncookies", False)
        redir = not sc.get("accept_redirects", True)
        fwd = not sc.get("ip_forward", True)
        return [
            ("Syncookies", "✅" if syn else "❌", syn),
            ("ICMP Redirects", "✅" if redir else "❌", redir),
            ("IP Forward", "✅" if fwd else "⚠️", fwd),
        ]

    do_sysctl = _sysctl_items(sysctl)
    pr_sysctl = _sysctl_items(pr_sysctl)

    def _sysctl_grid(items):
        rows = ""
        for label, icon, ok in items:
            val_cls = "sec-sysctl-value" + ("" if ok else " style='color:var(--danger)'")
            rows += f'<div class="sec-sysctl-item"><span class="sec-sysctl-label">{label}</span><span {val_cls}>{icon}</span></div>'
        return rows

    body = f"""
<div class="sec-header">
  <h1>🛡️ Security Monitor</h1>
  <span class="sec-refresh" id="refresh-indicator">Live</span>
  <button class="sec-pause-btn" id="pause-btn" onclick="toggleRefresh()" title="Pause auto-refresh">⏸</button>
</div>

<div class="sec-kanban">

  <div class="sec-col">
    <div class="sec-col-header"><h3>🏠 DO VPS <span class="sec-badge">:{ssh_port}</span> {f2b_badge}</h3></div>
    <div class="sec-section">
      <div class="sec-section-title">Overview</div>
      <div class="sec-card sec-overview">
        <div class="sec-stat-row"><span class="stat-label">Uptime</span><span class="stat-value">{_html.escape(uptime)}</span></div>
      </div>
      <div class="sec-sysctl-grid">{_sysctl_grid(do_sysctl)}</div>
    </div>
    <div class="sec-section">
      <div class="sec-section-title">Top Attackers</div>
      <div class="sec-card">{attacker_rows if attacker_rows else '<span class="sec-empty">No recent attackers</span>'}</div>
    </div>
    <div class="sec-section">
      <div class="sec-section-title">Firewall Rules ({len(ufw_rules)})</div>
      <div class="sec-card">{do_ufw_rows if do_ufw_rows else '<span class="sec-empty">No rules</span>'}</div>
    </div>
  </div>

  <div class="sec-col">
    <div class="sec-col-header"><h3>🌐 Proxy VPS <span class="sec-badge">:{pr_ssh_port}</span> {pr_badge}</h3></div>
    <div class="sec-section">
      <div class="sec-section-title">Overview</div>
      <div class="sec-card sec-overview">
        <div class="sec-stat-row"><span class="stat-label">Uptime</span><span class="stat-value">{_html.escape(pr_uptime)}</span></div>
      </div>
      <div class="sec-sysctl-grid">{_sysctl_grid(pr_sysctl)}</div>
    </div>
    <div class="sec-section">
      <div class="sec-section-title">Proxy Traffic</div>
      {traffic_rows if traffic_rows else '<div class="sec-card"><span class="sec-empty">No inbound data</span></div>'}
    </div>
    <div class="sec-section">
      <div class="sec-section-title">Firewall Rules ({len(pr_ufw_rules)})</div>
      <div class="sec-card">{pr_ufw_rows if pr_ufw_rows else '<span class="sec-empty">No rules</span>'}</div>
    </div>
  </div>

</div>

<script>
var _secTimer = null;
var _secPaused = false;
function toggleRefresh() {{
  if (_secPaused) {{
    _secPaused = false;
    document.getElementById('refresh-indicator').textContent = 'Live';
    document.getElementById('pause-btn').textContent = '⏸';
    _secTimer = setTimeout(function(){{ location.reload(); }}, 30000);
  }} else {{
    _secPaused = true;
    document.getElementById('refresh-indicator').textContent = '⏸ Paused';
    document.getElementById('pause-btn').textContent = '▶';
    if (_secTimer) clearTimeout(_secTimer);
  }}
}}
_secTimer = setTimeout(function(){{ location.reload(); }}, 30000);
</script>"""

    return _page("Security Monitor", body, nav_active="home")


# ---------------------------------------------------------------------------
# Settings Page
# ---------------------------------------------------------------------------

def services_page() -> str:
    """Render the Services portal page — AxonHub-style service status cards with live health check."""
    services = [
        ("n8n", "自动化工作流", "可视化编排API与任务，连接500+服务", os.environ.get("BRAIN_SVC_N8N_URL", "#"), "#ef4444",
         '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/></svg>',
         os.environ.get("BRAIN_SVC_N8N_HOST", "")),
        ("Uptime Kuma", "服务监控", "实时状态监控、告警通知与SLA追踪", os.environ.get("BRAIN_SVC_UPTIME_URL", "#"), "#22c55e",
         '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
         os.environ.get("BRAIN_SVC_UPTIME_HOST", "")),
        ("File Browser", "文件管理", "浏览、上传与管理工作文件", os.environ.get("BRAIN_SVC_FILES_URL", "#"), "#3b82f6",
         '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
         os.environ.get("BRAIN_SVC_FILES_HOST", "")),
    ]
    cards = []
    for name, title, desc, url, color, icon, host in services:
        cards.append(f'''<a href="{_html.escape(url)}" target="_blank" rel="noopener" class="svc-card" data-host="{_html.escape(host)}">
  <div class="svc-card-header">
    <div class="svc-card-icon" style="background:{color}18;color:{color}">{icon}</div>
    <div class="svc-card-info">
      <h3 class="svc-card-name">{_html.escape(name)}</h3>
      <p class="svc-card-title">{_html.escape(title)}</p>
    </div>
    <div class="svc-card-arrow">{_ICON_EXTERNAL}</div>
  </div>
  <p class="svc-card-desc">{_html.escape(desc)}</p>
  <div class="svc-card-footer">
    <div class="svc-health-indicator">
      <span class="svc-health-dot" data-host="{_html.escape(host)}"></span>
      <span class="svc-health-status" data-host="{_html.escape(host)}" data-i18n-default="svc_detecting">检测中...</span>
    </div>
    <span class="svc-health-lat" data-host="{_html.escape(host)}">—</span>
  </div>
</a>''')

    hosts_json = _json.dumps([h for _, _, _, _, _, _, h in services])
    name_to_host_json = _json.dumps({n: h for n, _, _, _, _, _, h in services})
    body = f"""
<div class="svc-wrap">
  <div class="svc-page-header">
    <h1 class="svc-page-title" data-i18n="svc_title">🔗 服务中心</h1>
    <p class="svc-page-desc" data-i18n="svc_desc">所有外部服务运行在独立服务器上，点击卡片直接跳转</p>
  </div>
  <div class="svc-grid">
    {''.join(cards)}
  </div>
</div>

<style>
.svc-wrap{{max-width:860px;margin:0 auto;padding:0 var(--sp-lg) var(--sp-xl);animation:pageEnter .4s var(--ease-out)}}
.svc-page-header{{margin-bottom:var(--sp-lg);animation:staggerFade .3s var(--ease-out) .05s both}}
.svc-page-title{{font-size:1.3rem;font-weight:800;color:var(--ink);margin:0 0 4px;letter-spacing:-.02em}}
.svc-page-desc{{font-size:.88rem;color:var(--ink-muted);margin:0}}
.svc-grid{{display:grid;grid-template-columns:1fr;gap:var(--sp-md);animation:staggerFade .3s var(--ease-out) .1s both}}
@media(min-width:720px){{.svc-grid{{grid-template-columns:1fr 1fr}}}}
/* AxonHub-style service card */
.svc-card{{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:0;text-decoration:none;color:var(--ink);transition:all var(--duration) var(--ease-out);overflow:hidden;position:relative}}
.svc-card:hover{{border-color:var(--border-hover);transform:translateY(-2px);box-shadow:var(--shadow-lg),0 0 0 1px var(--border-hover)}}
.svc-card-header{{display:flex;align-items:center;gap:14px;padding:var(--sp-md) var(--sp-md) var(--sp-sm)}}
.svc-card-icon{{width:44px;height:44px;border-radius:var(--r-md);display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.svc-card-icon svg{{width:24px;height:24px}}
.svc-card-info{{flex:1;min-width:0}}
.svc-card-name{{font-size:1rem;font-weight:700;margin:0;color:var(--ink);letter-spacing:-.01em}}
.svc-card-title{{font-size:.82rem;color:var(--primary);margin:2px 0 0;font-weight:500}}
.svc-card-arrow{{color:var(--ink-dim);flex-shrink:0;transition:transform var(--duration),color var(--duration)}}
.svc-card-arrow svg{{width:16px;height:16px}}
.svc-card:hover .svc-card-arrow{{color:var(--primary);transform:translateX(3px)}}
.svc-card-desc{{font-size:.82rem;color:var(--ink-muted);margin:0;padding:0 var(--sp-md) var(--sp-sm);line-height:1.5}}
.svc-card-footer{{display:flex;align-items:center;justify-content:space-between;padding:var(--sp-sm) var(--sp-md);border-top:1px solid var(--border);background:var(--surface);font-size:.78rem}}
.svc-health-indicator{{display:flex;align-items:center;gap:6px}}
.svc-health-dot{{width:8px;height:8px;border-radius:50%;background:var(--ink-dim);transition:background .3s,box-shadow .3s}}
.svc-health-dot.alive{{background:var(--success);box-shadow:0 0 8px rgba(52,211,153,.5)}}
.svc-health-dot.dead{{background:var(--danger);box-shadow:0 0 8px rgba(248,113,113,.4)}}
.svc-health-dot.checking{{background:var(--warning);animation:pulse 1.5s infinite}}
.svc-health-status{{font-weight:500;color:var(--ink-muted)}}
.svc-health-dot.alive + .svc-health-status,.svc-health-dot.alive ~ .svc-health-status{{color:var(--success)}}
.svc-health-dot.dead + .svc-health-status,.svc-health-dot.dead ~ .svc-health-status{{color:var(--danger)}}
.svc-health-lat{{font-family:var(--font-mono);font-size:.72rem;color:var(--ink-dim)}}
</style>

<script>
(function(){{
  var hosts = {hosts_json};
  // Set all dots to "checking" state
  hosts.forEach(function(h){{
    document.querySelectorAll('.svc-health-dot[data-host="'+h+'"]').forEach(function(d){{d.classList.add('checking')}});
  }});
  // Server-side health check via local API (same-origin, no CORS issues)
  var nameToHost = {name_to_host_json};
  fetch('/api/health').then(function(r){{return r.json()}}).then(function(data){{
    for (var name in data) {{
      var h = nameToHost[name];
      if (!h) continue;
      var info = data[name];
      var alive = info.alive;
      var ms = info.ms;
      document.querySelectorAll('.svc-health-dot[data-host="'+h+'"]').forEach(function(d){{
        d.classList.remove('checking');
        d.classList.add(alive?'alive':'dead');
        d.style.background = alive ? 'var(--success)' : 'var(--danger)';
        if (alive) d.style.boxShadow = '0 0 8px rgba(52,211,153,.5)';
      }});
      document.querySelectorAll('.svc-health-status[data-host="'+h+'"]').forEach(function(s){{
        s.textContent = alive ? _t('svc_online') : _t('svc_offline');
        s.style.color = alive ? 'var(--success)' : 'var(--danger)';
      }});
      document.querySelectorAll('.svc-health-lat[data-host="'+h+'"]').forEach(function(l){{
        l.textContent = alive ? ms+'ms' : '—';
      }});
    }}
  }}).catch(function(){{
    hosts.forEach(function(h){{
      document.querySelectorAll('.svc-health-dot[data-host="'+h+'"]').forEach(function(d){{
        d.classList.remove('checking'); d.style.background='var(--ink-dim)';
      }});
      document.querySelectorAll('.svc-health-status[data-host="'+h+'"]').forEach(function(s){{
        s.textContent=_t('svc_unknown');
      }});
    }});
  }});
}})();
</script>
"""

    return _page("Services", body, nav_active="services")


def profile_page(*, error: str = "", success: str = "") -> str:
    """Render the Profile page — AxonHub-style grouped settings with avatar card."""
    error_html = f'<div class="pf-alert pf-alert-error">{_html.escape(error)}</div>' if error else ""
    success_html = f'<div class="pf-alert pf-alert-success">{_html.escape(success)}</div>' if success else ""

    body = f"""
<div class="pf-wrap">

  <!-- Avatar Card -->
  <div class="pf-avatar-card">
    <div class="pf-avatar-ring">
      <div class="pf-avatar" id="profile-avatar">👤</div>
    </div>
    <div class="pf-avatar-info">
      <h2 class="pf-avatar-name" id="profile-display-name">探索者</h2>
      <p class="pf-avatar-role" data-i18n="pf_brain_user">Hermes Brain 用户</p>
      <div class="pf-avatar-badges">
        <span class="pf-badge pf-badge-primary" data-i18n="pf_admin">管理员</span>
        <span class="pf-badge pf-badge-info" data-i18n="pf_online">在线</span>
      </div>
    </div>
  </div>

  <!-- Display Preferences -->
  <div class="pf-section">
    <div class="pf-section-head">
      <span class="pf-section-icon">🎨</span>
      <div>
        <h3 class="pf-section-title" data-i18n="pf_prefs">显示偏好</h3>
        <p class="pf-section-desc" data-i18n="pf_prefs_desc">自定义界面显示</p>
      </div>
    </div>
    <form class="pf-form" id="prefs-form">
      <div class="pf-field">
        <label class="pf-label" for="display-name" data-i18n="pf_name">显示名称</label>
        <input type="text" name="display_name" class="pf-input" placeholder="你的名字" id="display-name" data-i18n-ph="pf_name_ph">
      </div>
      <div class="pf-field">
        <label class="pf-label" for="avatar-url" data-i18n="pf_avatar">头像链接</label>
        <div style="display:flex;gap:8px;align-items:center">
          <input type="text" name="avatar_url" class="pf-input" placeholder="输入头像图片URL" id="avatar-url" data-i18n-ph="pf_avatar_ph" style="flex:1">
          <label for="avatar-file-input" class="pf-btn pf-btn-secondary" style="cursor:pointer;white-space:nowrap;margin:0" data-i18n="pf_avatar_upload">上传图片</label>
          <input type="file" id="avatar-file-input" accept="image/*" style="display:none">
        </div>
      </div>
      <div class="pf-field">
        <label class="pf-label" for="theme-select" data-i18n="pf_theme">主题</label>
        <select name="theme" class="pf-input" id="theme-select">
          <option value="dark" data-i18n="pf_theme_dark">深色 Dracula</option>
          <option value="light" data-i18n="pf_theme_light">浅色 Light</option>
        </select>
      </div>
      <div class="pf-field">
        <label class="pf-label" for="lang-select" data-i18n="pf_lang">语言</label>
        <select name="lang" class="pf-input" id="lang-select" onchange="switchLang(this.value)">
          <option value="zh" data-i18n="pf_lang_zh">中文</option>
          <option value="en" data-i18n="pf_lang_en">English</option>
        </select>
      </div>
      <button type="button" class="pf-btn pf-btn-primary" onclick="savePrefs()" data-i18n="pf_save">保存偏好</button>
    </form>
  </div>

  <!-- Change Password -->
  <div class="pf-section">
    <div class="pf-section-head">
      <span class="pf-section-icon">🔐</span>
      <div>
        <h3 class="pf-section-title" data-i18n="pf_password">修改密码</h3>
        <p class="pf-section-desc" data-i18n="pf_password_desc">更新你的登录密码</p>
      </div>
    </div>
    {error_html}
    {success_html}
    <form id="pw-form" class="pf-form" onsubmit="return changePassword(event)">
      <div class="pf-field">
        <label class="pf-label" for="cur-pw" data-i18n="pf_cur_pw">当前密码</label>
        <input type="password" name="current_password" class="pf-input" id="cur-pw" required autocomplete="current-password">
      </div>
      <div class="pf-field-row">
        <div class="pf-field">
          <label class="pf-label" for="new-pw" data-i18n="pf_new_pw">新密码</label>
          <input type="password" name="new_password" class="pf-input" id="new-pw" required autocomplete="new-password" minlength="6">
        </div>
        <div class="pf-field">
          <label class="pf-label" for="confirm-pw" data-i18n="pf_confirm_pw">确认新密码</label>
          <input type="password" name="confirm_password" class="pf-input" id="confirm-pw" required autocomplete="new-password">
        </div>
      </div>
      <button type="submit" class="pf-btn pf-btn-primary" data-i18n="pf_update_pw">更新密码</button>
    </form>
  </div>

  <!-- System Info -->
  <div class="pf-section">
    <div class="pf-section-head">
      <span class="pf-section-icon">📊</span>
      <div>
        <h3 class="pf-section-title" data-i18n="pf_system">系统信息</h3>
        <p class="pf-section-desc" data-i18n="pf_system_desc">运行状态概览</p>
      </div>
    </div>
    <div class="pf-info-grid">
      <div class="pf-info-card">
        <div class="pf-info-icon" style="background:rgba(189,147,249,.15);color:var(--primary)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20"><path d="M12 2a4 4 0 0 1 4 4c0 1.95-2 3-2 5h-4c0-2-2-3.05-2-5a4 4 0 0 1 4-4z"/><line x1="10" y1="17" x2="14" y2="17"/><line x1="10" y1="19" x2="14" y2="19"/><line x1="10" y1="21" x2="14" y2="21"/></svg>
        </div>
        <div class="pf-info-text">
          <span class="pf-info-label">Brain</span>
          <span class="pf-info-value" data-i18n="pf_status_run">正常运行</span>
        </div>
      </div>
      <div class="pf-info-card">
        <div class="pf-info-icon" style="background:rgba(80,250,123,.15);color:var(--success)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        </div>
        <div class="pf-info-text">
          <span class="pf-info-label">API Gateway</span>
          <span class="pf-info-value" data-i18n="pf_online">在线</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Danger Zone -->
  <div class="pf-section pf-danger-zone">
    <div class="pf-section-head">
      <span class="pf-section-icon">🚪</span>
      <div>
        <h3 class="pf-section-title pf-text-danger" data-i18n="pf_logout">退出登录</h3>
        <p class="pf-section-desc" data-i18n="pf_logout_desc">结束当前会话并返回登录页</p>
      </div>
    </div>
    <a href="/logout" class="pf-btn pf-btn-danger" data-i18n="pf_logout">退出登录</a>
  </div>
</div>

<style>
.pf-wrap{{max-width:860px;margin:0 auto;padding:0 var(--sp-lg) var(--sp-xl);animation:pageEnter .4s var(--ease-out)}}

/* Avatar card */
.pf-avatar-card{{display:flex;align-items:center;gap:20px;background:var(--card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-lg);margin-bottom:var(--sp-md);animation:staggerFade .3s var(--ease-out) .05s both}}
.pf-avatar-ring{{width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,var(--primary),var(--info));padding:3px;flex-shrink:0}}
.pf-avatar{{width:100%;height:100%;border-radius:50%;background:var(--surface);display:flex;align-items:center;justify-content:center;font-size:1.8rem;overflow:hidden}}
.pf-avatar-info{{flex:1;min-width:0}}
.pf-avatar-name{{font-size:1.2rem;font-weight:800;margin:0;letter-spacing:-.01em}}
.pf-avatar-role{{font-size:.85rem;color:var(--ink-muted);margin:2px 0 8px}}
.pf-avatar-badges{{display:flex;gap:8px}}
.pf-badge{{display:inline-flex;align-items:center;padding:2px 10px;border-radius:9999px;font-size:.72rem;font-weight:600;letter-spacing:.02em}}
.pf-badge-primary{{background:rgba(189,147,249,.15);color:var(--primary)}}
.pf-badge-info{{background:rgba(80,250,123,.15);color:var(--success)}}

/* Section card */
.pf-section{{background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:0;margin-bottom:var(--sp-md);overflow:hidden;animation:staggerFade .3s var(--ease-out) both;transition:border-color var(--duration)}}
.pf-section:hover{{border-color:var(--border-hover)}}
.pf-section-head{{display:flex;align-items:center;gap:14px;padding:var(--sp-md) var(--sp-md) var(--sp-sm);border-bottom:1px solid var(--border)}}
.pf-section-icon{{font-size:1.2rem;flex-shrink:0}}
.pf-section-title{{font-size:1rem;font-weight:700;margin:0;color:var(--ink)}}
.pf-section-desc{{font-size:.78rem;color:var(--ink-muted);margin:1px 0 0}}
.pf-text-danger{{color:var(--danger)!important}}

/* Form */
.pf-form{{padding:var(--sp-md);display:flex;flex-direction:column;gap:var(--sp-sm)}}
.pf-field{{display:flex;flex-direction:column;gap:4px}}
.pf-field-row{{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-sm)}}
@media(max-width:520px){{.pf-field-row{{grid-template-columns:1fr}}}}
.pf-label{{font-size:.82rem;font-weight:500;color:var(--ink-muted)}}
.pf-input{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);padding:10px 14px;color:var(--ink);font-size:.92rem;outline:none;transition:border-color .15s,box-shadow .15s}}
.pf-input:focus{{border-color:var(--primary);box-shadow:0 0 0 3px rgba(189,147,249,.2)}}

/* Buttons */
.pf-btn{{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:10px 20px;border-radius:var(--r-md);font-size:.92rem;font-weight:600;cursor:pointer;transition:all var(--duration) var(--ease-out);border:none;min-height:42px}}
.pf-btn-primary{{background:var(--primary);color:var(--surface)}}
.pf-btn-primary:hover{{opacity:.85;transform:translateY(-1px)}}
.pf-btn-danger{{border:1px solid var(--danger);background:rgba(248,113,113,.08);color:var(--danger)}}
.pf-btn-danger:hover{{background:rgba(248,113,113,.18);transform:translateY(-1px)}}
.pf-btn-secondary{{background:var(--surface);border:1px solid var(--border);color:var(--ink)}}
.pf-btn-secondary:hover{{border-color:var(--primary);color:var(--primary);transform:translateY(-1px)}}
.pf-btn svg{{width:16px;height:16px}}

/* Alert */
.pf-alert{{padding:10px 14px;border-radius:var(--r-md);font-size:.88rem;margin-bottom:var(--sp-sm)}}
.pf-alert-error{{background:rgba(255,85,85,.12);color:var(--danger);border:1px solid rgba(255,85,85,.25)}}
.pf-alert-success{{background:rgba(80,250,123,.12);color:var(--success);border:1px solid rgba(80,250,123,.25)}}

/* Info grid */
.pf-info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-sm);padding:var(--sp-md)}}
.pf-info-card{{display:flex;align-items:center;gap:12px;background:var(--surface);border-radius:var(--r-md);padding:12px 14px}}
.pf-info-icon{{width:40px;height:40px;border-radius:var(--r-md);display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.pf-info-text{{min-width:0}}
.pf-info-label{{display:block;font-size:.72rem;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.04em}}
.pf-info-value{{display:block;font-size:1rem;font-weight:700;color:var(--ink);margin-top:1px}}

/* Danger zone */
.pf-danger-zone{{border-color:rgba(248,113,113,.3)}}
.pf-danger-zone .pf-section-head{{border-bottom-color:rgba(248,113,113,.15)}}
.pf-danger-zone .pf-form,.pf-danger-zone .pf-btn{{padding-left:var(--sp-md)}}

@media(max-width:520px){{.pf-info-grid{{grid-template-columns:1fr}}}}
</style>

<script>
(function(){{var n=localStorage.getItem('hermes_display_name');
var t=localStorage.getItem('hermes_theme');
var a=localStorage.getItem('hermes_avatar_url');
var l=localStorage.getItem('hermes_lang')||'zh';
if(n){{document.getElementById('display-name').value=n;document.getElementById('profile-display-name').textContent=n;
var sb=document.getElementById('sidebar-username');if(sb)sb.textContent=n;}}
if(t)document.getElementById('theme-select').value=t;
if(a){{document.getElementById('avatar-url').value=a;applyAvatar(a);}}
document.getElementById('lang-select').value=l;
applyI18n(l);
}})();

function applyAvatar(url){{
  var els=['profile-avatar','sidebar-avatar'];
  els.forEach(function(id){{
    var el=document.getElementById(id);if(!el)return;
    if(url){{el.innerHTML='<img src="'+url+'" style="width:100%;height:100%;border-radius:50%;object-fit:cover" onerror="this.outerHTML=this.dataset.fallback" data-fallback="👤">';}}
    else{{el.textContent='👤';}}
  }});
}}

document.getElementById('avatar-file-input').addEventListener('change',function(e){{
  var f=e.target.files[0];if(!f)return;
  if(f.size>204800){{alert(_t('pf_avatar_too_large'));e.target.value='';return;}}
  var r=new FileReader();
  r.onload=function(ev){{
    var b64=ev.target.result;
    document.getElementById('avatar-url').value=b64;
    applyAvatar(b64);
  }};
  r.readAsDataURL(f);
}});
document.querySelector('label[for="avatar-file-input"],label[data-i18n="pf_avatar_upload"]').addEventListener('click',function(){{document.getElementById('avatar-file-input').click();}});

function changePassword(e){{
  e.preventDefault();
  var form=document.getElementById('pw-form');
  var cur=encodeURIComponent(form.querySelector('[name=current_password]').value);
  var npw=encodeURIComponent(form.querySelector('[name=new_password]').value);
  var cpw=encodeURIComponent(form.querySelector('[name=confirm_password]').value);
  fetch('/settings/password',{{
    method:'POST',
    headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'current_password='+cur+'&new_password='+npw+'&confirm_password='+cpw
  }}).then(function(r){{
    return r.text();
  }}).then(function(html){{
    var doc=new DOMParser().parseFromString(html,'text/html');
    var err=doc.querySelector('.pf-alert-error');
    var suc=doc.querySelector('.pf-alert-success');
    var pwSection=form.parentElement;
    var old=pwSection.querySelectorAll('.pf-alert');
    old.forEach(function(el){{el.remove();}});
    if(err){{
      var div=document.createElement('div');
      div.className='pf-alert pf-alert-error';
      div.textContent=err.textContent;
      form.insertBefore(div,form.firstChild);
    }} else if(suc){{
      var div=document.createElement('div');
      div.className='pf-alert pf-alert-success';
      div.textContent=_t('pf_pw_updated');
      form.insertBefore(div,form.firstChild);
      form.reset();
    }}
  }}).catch(function(){{
    var div=document.createElement('div');
    div.className='pf-alert pf-alert-error';
    div.textContent=_t('toast_network_error');
    form.insertBefore(div,form.firstChild);
  }});
  return false;
}}

function savePrefs(){{
  var n=document.getElementById('display-name').value;
  var t=document.getElementById('theme-select').value;
  var a=document.getElementById('avatar-url').value;
  var l=document.getElementById('lang-select').value;
  localStorage.setItem('hermes_display_name',n);
  localStorage.setItem('hermes_theme',t);
  localStorage.setItem('hermes_avatar_url',a);
  localStorage.setItem('hermes_lang',l);
  document.getElementById('profile-display-name').textContent=n||_t('pf_explorer');
  var sb=document.getElementById('sidebar-username');if(sb)sb.textContent=n||_t('nav_user');
  if(t==='light')document.documentElement.setAttribute('data-theme','light');
  else document.documentElement.removeAttribute('data-theme');
  applyAvatar(a);
  applyI18n(l);
  var toast=document.createElement('div');
  toast.textContent=_t('pf_saved');
  toast.style.cssText='position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--success);color:var(--surface);padding:10px 24px;border-radius:9999px;font-size:.88rem;font-weight:600;z-index:9999;animation:pageEnter .3s var(--ease-out)';
  document.body.appendChild(toast);
  setTimeout(function(){{toast.style.opacity='0';toast.style.transition='opacity .3s';setTimeout(function(){{toast.remove()}},300)}},1800);
}}
</script>

"""

    return _page("My Profile", body, nav_active="profile")


def settings_page(*, error: str = "", success: str = "") -> str:
    """Render user settings page — redirects to profile page."""
    # Delegate to profile_page for unified experience
    return profile_page(error=error, success=success)


# ---------------------------------------------------------------------------
# Knowledge Tree page
# ---------------------------------------------------------------------------

_STAGE_BADGE_MAP_KN = {
    "draft": "badge-pending",
    "refined": "badge-pattern",
    "verified": "badge-approved_db_only",
    "canonized": "badge-approved_for_export",
    "deprecated": "badge-superseded",
}

def _stage_badge_knowledge(stage: str) -> str:
    cls = _STAGE_BADGE_MAP_KN.get(stage, "badge-pending")
    return f'<span class="badge {cls}">{_html.escape(stage)}</span>'

# Stage badge mapping (knowledge lifecycle)
_STAGE_BADGE_MAP = {
    "draft": "badge-pending",
    "refined": "badge-pattern",
    "verified": "badge-approved_db_only",
    "canonized": "badge-approved_for_export",
    "deprecated": "badge-superseded",
}

_STAGE_LABEL = {
    "draft": "Draft",
    "refined": "Refined",
    "verified": "Verified",
    "canonized": "Canonized",
    "deprecated": "Deprecated",
}

# Category badge (reuse existing _CATEGORY_BADGE_MAP + extras)
_KN_CATEGORY_BADGE_MAP = {
    "rule": "badge-rule",
    "workflow_hint": "badge-approved_db_only",
    "preference": "badge-pending",
    "fact": "badge-pattern",
}


def _stage_badge(stage: str) -> str:
    cls = _STAGE_BADGE_MAP.get(stage, "badge-pending")
    i18n_key = f"stage_{stage}_short"
    label = _pt(i18n_key)
    return f'<span class="badge {cls}" data-i18n="{i18n_key}">{_html.escape(label)}</span>'


def _kn_category_badge(category: str) -> str:
    cls = _KN_CATEGORY_BADGE_MAP.get(category, "badge-rule")
    return f'<span class="badge {cls}">{_html.escape(category)}</span>'


def _confidence_bar(confidence: float) -> str:
    """Render a horizontal confidence bar 0-100%."""
    pct = max(0, min(100, int(confidence * 100)))
    if pct >= 70:
        color = "var(--success)"
    elif pct >= 40:
        color = "var(--warning)"
    else:
        color = "var(--danger)"
    return (
        f'<div class="kn-conf-bar">'
        f'<div class="kn-conf-fill" style="width:{pct}%;background:{color}"></div>'
        f'</div>'
        f'<span class="kn-conf-label">{pct}%</span>'
    )


def knowledge_tree_page(
    *,
    nodes: list[dict],
    counts: dict[str, int],
    active_stage: str = "all",
    active_category: str = "",
    active_domain: str = "",
    domains: list[str] | None = None,
) -> str:
    """Render the knowledge tree overview with stats bar, filters, and node cards."""
    if domains is None:
        domains = []
    total = sum(counts.values())

    # -- Stats bar (clickable filter cards — replaces tabs) --
    stat_cards = [
        ("all", _pt("stage_all"), str(total), "var(--ink)"),
        ("draft", _pt("stage_draft_short"), str(counts.get("draft", 0)), "var(--warning)"),
        ("refined", _pt("stage_refined_short"), str(counts.get("refined", 0)), "var(--info)"),
        ("verified", _pt("stage_verified_short"), str(counts.get("verified", 0)), "var(--success)"),
        ("canonized", _pt("stage_canonized_short"), str(counts.get("canonized", 0)), "var(--primary)"),
        ("deprecated", _pt("stage_deprecated_short"), str(counts.get("deprecated", 0)), "var(--ink-dim)"),
    ]
    trash_count = counts.get("deprecated", 0)
    stats_html = ""
    for key, label, num, color in stat_cards:
        active_cls = " dash-card-active" if key == active_stage else ""
        href = f"/knowledge?stage={key}" if key != "all" else "/knowledge"
        if active_category:
            href += f"&category={active_category}"
        if active_domain:
            href += f"&domain={active_domain}"
        stats_html += (
            f'<a href="{href}" class="dash-card{active_cls}">'
            f'<div class="num" style="color:{color}">{num}</div>'
            f'<div class="label">{_html.escape(label)}</div>'
            f'</a>'
        )

    # -- Category options for filter --
    cat_options = f'<option value="">{_pt("kn_all_cat")}</option>'
    for cat in sorted(_KN_CATEGORY_BADGE_MAP):
        sel = ' selected' if cat == active_category else ''
        cat_options += f'<option value="{_html.escape(cat)}"{sel}>{_html.escape(cat.title())}</option>'

    # -- Domain options for filter --
    dom_options = f'<option value="">{_pt("kn_all_dom")}</option>'
    for dom in sorted(domains):
        sel = ' selected' if dom == active_domain else ''
        dom_options += f'<option value="{_html.escape(dom)}"{sel}>{_html.escape(dom)}</option>'

    # -- Node cards grouped by domain --
    # Group nodes by domain for collapsible sections
    domain_groups: dict[str, list] = {}
    for n in nodes:
        domain = str(n.get("domain", "general"))
        domain_groups.setdefault(domain, []).append(n)

    _domain_icons = {"devops": "🔧", "network": "🌐", "study": "🧬", "general": "📦", "security": "🔒"}
    _domain_order = {"devops": 0, "network": 1, "study": 2, "security": 3, "general": 99}

    cards_html = ""
    if not nodes:
        cards_html = f'<div class="empty" data-i18n="kn_no_nodes">{_pt("kn_no_nodes")}</div>'
    else:
        for domain in sorted(domain_groups, key=lambda d: _domain_order.get(d, 50)):
            group = domain_groups[domain]
            icon = _domain_icons.get(domain, "📁")
            # Count by stage within this domain
            stage_counts = {}
            for n in group:
                s = str(n.get("stage", "draft"))
                stage_counts[s] = stage_counts.get(s, 0) + 1
            stage_summary = " · ".join(f"{_pt(f'stage_{s}_short')}: {c}" for s, c in sorted(stage_counts.items()))

            group_cards = ""
            for n in group:
                nid = str(n.get("id", ""))
                summary = str(n.get("summary", ""))
                stage = str(n.get("stage", "draft"))
                category = str(n.get("category", "fact"))
                ndomain = str(n.get("domain", "general"))
                confidence = float(n.get("confidence", 0))
                source = str(n.get("source", ""))
                retrieval_count = int(n.get("retrieval_count", 0))
                created_at = str(n.get("created_at", ""))[:19]
                preview = summary[:140] + ("..." if len(summary) > 140 else "")

                uses_text = f"🔍 {retrieval_count}" if retrieval_count > 0 else ""

                group_cards += f"""<a href="/knowledge/{_html.escape(nid)}" class="card">
  <div class="card-top">{_stage_badge(stage)} {_kn_category_badge(category)} <span class="badge badge-rule" style="font-size:.65rem">{_html.escape(ndomain)}</span></div>
  <div class="card-preview">{_html.escape(preview)}</div>
  <div style="margin-top:8px;display:flex;align-items:center;gap:8px">
    {_confidence_bar(confidence)}
  </div>
  <div class="card-meta">
    <span>{_html.escape(created_at)}</span>
    {"<span>" + uses_text + "</span>" if uses_text else ""}
  </div>
</a>"""

            cards_html += f"""<div class="kn-domain-group" data-domain="{_html.escape(domain)}">
  <button class="kn-domain-header" onclick="toggleDomain(this)">
    <span class="kn-domain-toggle">▼</span>
    <span class="kn-domain-icon">{icon}</span>
    <span class="kn-domain-name">{_html.escape(domain.title())}</span>
    <span class="kn-domain-count">{len(group)} {_pt('kn_nodes')}</span>
    <span class="kn-domain-stages">{_html.escape(stage_summary)}</span>
  </button>
  <div class="kn-domain-cards">{group_cards}</div>
</div>"""

    body = f"""
<h1 style="padding:16px 16px 0;font-size:1.2rem;font-weight:700;letter-spacing:-.02em;display:flex;align-items:center;gap:8px">🌳 <span data-i18n="kn_title">{_pt("kn_title")}</span> <span class="kn-info-btn" onclick="showStageHelp()" title="Stage definitions">ⓘ</span></h1>
<div class="dash-grid">{stats_html}</div>
<div style="padding:0 16px 8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
  <form method="get" action="/knowledge" style="display:flex;gap:8px;flex-wrap:wrap;flex:1" id="kn-filter-form" onsubmit="return false">
    <input type="hidden" name="stage" value="{_html.escape(active_stage)}">
    <select name="category" class="kn-filter-select" onchange="this.form.submit()">{cat_options}</select>
    <select name="domain" class="kn-filter-select" onchange="this.form.submit()">{dom_options}</select>
    <input type="text" name="q" data-i18n-ph="kn_search" placeholder="{_pt('kn_search')}" class="kn-search-input" id="kn-search">
  </form>
</div>
<div style="padding:0 16px 8px;display:flex;gap:8px;flex-wrap:wrap">
  <button class="kn-action-btn" data-i18n="kn_add" onclick="showAddModal()">{_pt("kn_add")}</button>
  <button class="kn-action-btn secondary" data-i18n="kn_export" onclick="exportKnowledge()">{_pt("kn_export")}</button>
  <button class="kn-action-btn secondary" data-i18n="kn_retrospect" onclick="retrospect()">{_pt("kn_retrospect")}</button>
  {f'<button class="kn-action-btn danger" onclick="emptyTrash()">{_pt("kn_empty_trash")} ({trash_count})</button>' if trash_count > 0 else ''}
</div>
<div id="kn-card-grid">{cards_html}</div>

<style>
.dash-card-active{{border-color:var(--primary)!important;background:var(--primary-muted)!important}}
.dash-card-active .label{{color:var(--primary)!important;font-weight:600}}
.kn-action-btn.danger{{background:var(--danger-muted);color:var(--danger);border-color:var(--danger)}}
.kn-action-btn.danger:hover{{background:rgba(248,113,113,.25)}}
.kn-info-btn{{font-size:.85rem;cursor:pointer;opacity:.4;transition:opacity var(--duration);color:var(--ink-muted)}}
.kn-info-btn:hover{{opacity:1;color:var(--primary)}}
.kn-filter-select{{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  color:var(--ink);font-size:.84rem;padding:8px 12px;min-height:40px;outline:none;
  transition:border-color var(--duration);cursor:pointer
}}
.kn-filter-select:focus{{border-color:var(--border-focus)}}
.kn-search-input{{
  flex:1;min-width:160px;padding:8px 14px;border:1px solid var(--border);border-radius:var(--r-md);
  background:var(--surface);color:var(--ink);font-size:.84rem;outline:none;min-height:40px;
  transition:border-color var(--duration),box-shadow var(--duration)
}}
.kn-search-input:focus{{border-color:var(--border-focus);box-shadow:0 0 0 3px rgba(167,139,250,.2)}}
.kn-search-input::placeholder{{color:var(--ink-dim)}}
.kn-domain-group{{margin-bottom:8px}}
.kn-domain-header{{
  display:flex;align-items:center;gap:10px;width:100%;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  padding:10px 14px;cursor:pointer;font-size:.9rem;font-weight:600;color:var(--ink);
  transition:background var(--duration),border-color var(--duration)
}}
.kn-domain-header:hover{{background:var(--card-hover);border-color:var(--primary);box-shadow:0 0 0 1px var(--primary)}}
.kn-domain-toggle{{font-size:.7rem;transition:transform .2s ease}}
.kn-domain-group.collapsed .kn-domain-toggle{{transform:rotate(-90deg)}}
.kn-domain-icon{{font-size:1.1rem}}
.kn-domain-name{{flex:1;text-align:left}}
.kn-domain-count{{font-size:.72rem;color:var(--ink-dim);font-weight:400}}
.kn-domain-stages{{font-size:.68rem;color:var(--ink-muted);font-weight:400}}
.kn-domain-cards{{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;
  padding:8px 0 4px;transition:max-height .3s ease,opacity .2s ease;overflow:hidden
}}
.kn-domain-group.collapsed .kn-domain-cards{{max-height:0;opacity:0;padding:0;border:0;pointer-events:none}}
.kn-conf-bar{{
  flex:1;height:6px;background:var(--border-hover);border-radius:3px;overflow:hidden;min-width:60px
}}
.kn-conf-fill{{height:100%;border-radius:3px;transition:width .3s var(--ease-out)}}
.kn-conf-label{{font-size:.72rem;color:var(--ink-muted);font-weight:600;min-width:32px;text-align:right}}
.kn-action-btn{{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border:1px solid var(--border);border-radius:var(--r-pill);background:var(--primary-muted);color:var(--primary);font-size:.84rem;font-weight:600;cursor:pointer;min-height:40px;transition:all var(--duration)}}
.kn-action-btn:hover{{background:rgba(167,139,250,.25);border-color:var(--border-focus)}}
.kn-action-btn.secondary{{background:var(--surface);color:var(--ink-muted);border-color:var(--border)}}
.kn-action-btn.secondary:hover{{color:var(--ink);border-color:var(--border-hover);background:var(--card)}}
.kn-modal-form textarea,.kn-modal-form input,.kn-modal-form select{{width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface);color:var(--ink);font-size:.84rem;margin-bottom:8px;min-height:40px;outline:none}}
.kn-modal-form textarea:focus,.kn-modal-form input:focus,.kn-modal-form select:focus{{border-color:var(--border-focus);box-shadow:0 0 0 3px rgba(167,139,250,.2)}}
.kn-modal-form textarea{{min-height:120px;resize:vertical}}
.kn-modal-form label{{display:block;font-size:.78rem;color:var(--ink-muted);margin-bottom:2px;text-transform:uppercase;letter-spacing:.04em}}
</style>
<div id="add-modal-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;align-items:center;justify-content:center">
  <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-lg);max-width:480px;width:90%;max-height:80vh;overflow-y:auto">
    <h2 style="margin-bottom:var(--sp-md);font-size:1.1rem" data-i18n="kn_add">{_pt("kn_add")}</h2>
    <form class="kn-modal-form" id="add-knowledge-form" onsubmit="return submitKnowledge(event)">
      <label data-i18n="kn_content_label">{_pt("kn_content_label")}</label>
      <textarea id="kn-form-content" required data-i18n-ph="kn_content_ph" placeholder="{_pt('kn_content_ph')}"></textarea>
      <label data-i18n="kn_source_label">{_pt("kn_source_label")}</label>
      <input type="text" id="kn-form-source" data-i18n-ph="kn_source_ph" placeholder="{_pt('kn_source_ph')}">
      <label data-i18n="kn_category_label">{_pt("kn_category_label")}</label>
      <select id="kn-form-category">
        <option value="fact">fact</option>
        <option value="rule">rule</option>
        <option value="workflow_hint">workflow_hint</option>
        <option value="preference">preference</option>
      </select>
      <label data-i18n="kn_domain_label">{_pt("kn_domain_label")}</label>
      <input type="text" id="kn-form-domain" value="general" data-i18n-ph="kn_domain_label" placeholder="general">
      <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">
        <button type="button" class="kn-action-btn secondary" onclick="hideAddModal()" data-i18n="kn_cancel">{_pt("kn_cancel")}</button>
        <button type="submit" class="kn-action-btn" data-i18n="kn_submit">{_pt("kn_submit")}</button>
      </div>
    </form>
  </div>
</div>
<div id="stage-help-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;align-items:center;justify-content:center" onclick="if(event.target===this)document.getElementById('stage-help-overlay').style.display='none'">
  <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-lg);max-width:520px;width:90%;max-height:80vh;overflow-y:auto">
    <h2 style="margin-bottom:var(--sp-md);font-size:1.1rem" data-i18n="kn_stage_lifecycle">{_pt("kn_stage_lifecycle")}</h2>
    <div style="font-size:.84rem;line-height:1.7;color:var(--ink)">
      <div style="margin-bottom:12px"><span style="color:var(--warning);font-weight:700">Draft</span><br><span data-i18n="kn_draft_desc">{_pt("kn_draft_desc")}</span></div>
      <div style="margin-bottom:12px"><span style="color:var(--info);font-weight:700">Refined</span><br><span data-i18n="kn_refined_desc">{_pt("kn_refined_desc")}</span></div>
      <div style="margin-bottom:12px"><span style="color:var(--success);font-weight:700">Verified</span><br><span data-i18n="kn_verified_desc">{_pt("kn_verified_desc")}</span></div>
      <div style="margin-bottom:12px"><span style="color:var(--primary);font-weight:700">Canonized</span><br><span data-i18n="kn_canonized_desc">{_pt("kn_canonized_desc")}</span></div>
      <div style="margin-bottom:12px"><span style="color:var(--ink-dim);font-weight:700">Deprecated</span><br><span data-i18n="kn_deprecated_desc">{_pt("kn_deprecated_desc")}</span></div>
      <div style="margin-top:16px;padding:8px 12px;background:var(--surface);border-radius:var(--r-md);color:var(--ink-muted);font-size:.78rem" data-i18n="kn_confidence_formula">{_pt("kn_confidence_formula")}</div>
    </div>
    <div style="margin-top:12px;text-align:right"><button class="kn-action-btn secondary" data-i18n="kn_close" onclick="document.getElementById('stage-help-overlay').style.display='none'">{_pt("kn_close")}</button></div>
  </div>
</div>
<div id="confirm-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(8px);z-index:200;justify-content:center;align-items:center" onclick="if(event.target===this)this.style.display='none'">
  <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-lg);max-width:400px;text-align:center">
    <h3 id="confirm-title" style="margin-bottom:var(--sp-md)"></h3>
    <div style="display:flex;gap:8px;justify-content:center">
      <button id="confirm-action-btn" style="padding:8px 20px;border-radius:var(--r-md);border:none;cursor:pointer;font-weight:600;background:var(--danger-muted);color:var(--danger)" data-i18n="rv_confirm">{_pt("rv_confirm")}</button>
      <button style="padding:8px 20px;border-radius:var(--r-md);border:1px solid var(--border);background:var(--surface);color:var(--ink-muted);cursor:pointer" onclick="document.getElementById('confirm-overlay').style.display='none'" data-i18n="kn_cancel">{_pt("kn_cancel")}</button>
    </div>
  </div>
</div>
<script>
(function(){{
  // Search filter
  var input = document.getElementById('kn-search');
  if (input) {{
    input.addEventListener('input', function(){{
      var q = this.value.toLowerCase();
      var cards = document.querySelectorAll('#kn-card-grid .card');
      cards.forEach(function(c){{
        c.style.display = c.textContent.toLowerCase().includes(q) ? '' : 'none';
      }});
      // Show/hide domain groups based on visible cards
      document.querySelectorAll('.kn-domain-group').forEach(function(g){{
        var visible = g.querySelectorAll('.card[style=""], .card:not([style])');
        var allHidden = true;
        g.querySelectorAll('.card').forEach(function(c){{
          if (c.style.display !== 'none') allHidden = false;
        }});
        g.style.display = allHidden ? 'none' : '';
      }});
    }});
  }}
}})();

function toggleDomain(btn) {{
  var group = btn.closest('.kn-domain-group');
  group.classList.toggle('collapsed');
}}
function showAddModal() {{
  document.getElementById('add-modal-overlay').style.display = 'flex';
  document.getElementById('kn-form-content').focus();
}}
function hideAddModal() {{
  document.getElementById('add-modal-overlay').style.display = 'none';
  document.getElementById('add-knowledge-form').reset();
  document.getElementById('kn-form-domain').value = 'general';
}}
function submitKnowledge(e) {{
  e.preventDefault();
  var content = document.getElementById('kn-form-content').value.trim();
  if (!content) return false;
  var data = {{
    content: content,
    source: document.getElementById('kn-form-source').value.trim(),
    category: document.getElementById('kn-form-category').value,
    domain: document.getElementById('kn-form-domain').value.trim() || 'general'
  }};
  fetch('/api/knowledge/integrate', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(data)
  }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      showToast(d.message || _t('toast_added'), 'approve');
      hideAddModal();
      setTimeout(function(){{ location.reload(); }}, 800);
    }})
    .catch(function(e) {{ showToast(_t('toast_error') + ': ' + e.message, 'reject'); }});
  return false;
}}
function exportKnowledge() {{
  fetch('/api/knowledge/export', {{method:'POST',headers:{{'Content-Type':'application/json'}}}})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{ showToast(d.message || _t('toast_export_done'), 'approve'); }})
    .catch(function(e) {{ showToast(_t('toast_error') + ': ' + e.message, 'reject'); }});
}}
function showStageHelp() {{
  document.getElementById('stage-help-overlay').style.display = 'flex';
}}
function retrospect() {{
  fetch('/api/knowledge/retrospect?dry_run=false', {{method:'POST',headers:{{'Content-Type':'application/json'}}}})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{ showToast(d.message || _t('toast_retrospect_done'), 'approve'); }})
    .catch(function(e) {{ showToast(_t('toast_error') + ': ' + e.message, 'reject'); }});
}}
function emptyTrash() {{
  var overlay = document.getElementById('confirm-overlay');
  var modal = document.getElementById('confirm-modal');
  var title = document.getElementById('confirm-title');
  var btn = document.getElementById('confirm-action-btn');
  title.textContent = _t('confirm_empty_trash');
  btn.onclick = function() {{
    overlay.style.display = 'none';
    fetch('/api/knowledge/trash/empty', {{method:'DELETE',headers:{{'Content-Type':'application/json'}}}})
      .then(function(r){{ return r.json(); }})
      .then(function(d){{ showToast(_t('toast_deleted').replace('{{count}}', (d.deleted||0)), 'approve'); setTimeout(function(){{ location.reload(); }},800); }})
      .catch(function(e){{ showToast(_t('toast_error') + ': ' + e.message, 'reject'); }});
  }};
  overlay.style.display = 'flex';
}}
function showToast(msg, type) {{
  var t = document.createElement('div');
  t.className = 'toast toast-' + (type||'approve');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function(){{ t.classList.add('show'); }},10);
  setTimeout(function(){{ t.classList.remove('show'); setTimeout(function(){{ t.remove(); }},300); }},2500);
}}
</script>
"""
    return _page("Knowledge Tree", body, nav_active="knowledge")


# ---------------------------------------------------------------------------
# Knowledge Detail page
# ---------------------------------------------------------------------------

_KN_ACTION_JS = """\
function knAct(url, actionName, successMsg, body, method) {
  var overlay = document.getElementById('confirm-overlay');
  var modal = document.getElementById('confirm-modal');
  var modalTitle = document.getElementById('confirm-title');
  var modalBtn = document.getElementById('confirm-action-btn');
  modalTitle.textContent = actionName + '?';
  modalBtn.onclick = function() {
    overlay.style.display = 'none';
    var opts = {method: method || 'POST', headers:{'Content-Type':'application/json'}};
    if (body) opts.body = JSON.stringify(body);
    fetch(url, opts)
      .then(function(r){ return r.json(); })
      .then(function(data){
        showToast(successMsg || _t('toast_done'), 'approve');
        setTimeout(function(){ location.reload(); }, 800);
      })
      .catch(function(e){
        showToast(_t('toast_error') + ': ' + e.message, 'reject');
      });
  };
  overlay.style.display = 'flex';
  modalBtn.focus();
}
function knDeprecate(url) {
  knAct(url, _t('kd_deprecate') + '?', _t('toast_done'), {stage: 'deprecated'});
}
function knPromote(url, nextStage) {
  knAct(url, _t('kd_promote') + ' ' + nextStage + '?', _t('toast_done'), {stage: nextStage});
}
function knMerge(url, actionName) {
  knAct(url, actionName || _t('kd_merge_into'), _t('toast_done'));
}
function knDelete(url) {
  knAct(url, _t('confirm_delete_node'), _t('toast_done'), null, 'DELETE');
}
function showEditModal() {
  document.getElementById('edit-modal-overlay').style.display = 'flex';
}
function hideEditModal() {
  document.getElementById('edit-modal-overlay').style.display = 'none';
}
function submitEdit(e) {
  e.preventDefault();
  var nodeId = window.location.pathname.split('/knowledge/')[1];
  var data = {
    summary: document.getElementById('edit-summary').value.trim(),
    content: document.getElementById('edit-content').value.trim(),
    category: document.getElementById('edit-category').value,
    domain: document.getElementById('edit-domain').value.trim() || 'general'
  };
  fetch('/api/knowledge/' + nodeId, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
    .then(function(r){ return r.json(); })
    .then(function(d){
      showToast(_t('toast_node_updated'), 'approve');
      setTimeout(function(){ location.reload(); }, 800);
    })
    .catch(function(e){ showToast(_t('toast_error') + ': ' + e.message, 'reject'); });
  return false;
}
function hideConfirm() {
  document.getElementById('confirm-overlay').style.display = 'none';
}
function showToast(msg, type) {
  var t = document.createElement('div');
  t.className = 'toast toast-' + (type||'approve');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function(){ t.classList.add('show'); },10);
  setTimeout(function(){ t.classList.remove('show'); setTimeout(function(){ t.remove(); },300); },2500);
}
document.addEventListener('keydown', function(e){
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'Escape') { hideConfirm(); }
  if (e.key === 'p' || e.key === 'P') {
    var promoteBtn = document.querySelector('button[onclick*="knPromote"]');
    if (promoteBtn) promoteBtn.click();
  }
  if (e.key === 'd' || e.key === 'D') {
    var deprecateBtn = document.querySelector('button[onclick*="knDeprecate"]');
    if (deprecateBtn) deprecateBtn.click();
  }
});
"""


def knowledge_detail_page(
    *,
    node: dict,
    thought_chains: list[dict] | None = None,
    parent_node: dict | None = None,
    child_nodes: list[dict] | None = None,
    supersedes_node: dict | None = None,
    superseded_by: list[dict] | None = None,
    contradicts_nodes: list[dict] | None = None,
) -> str:
    """Render the full detail view for a knowledge node with relationships, thought chain, and actions."""
    if thought_chains is None:
        thought_chains = []
    if child_nodes is None:
        child_nodes = []
    if superseded_by is None:
        superseded_by = []
    if contradicts_nodes is None:
        contradicts_nodes = []

    nid = str(node.get("id", ""))
    summary = str(node.get("summary", ""))
    content = str(node.get("content", ""))
    stage = str(node.get("stage", "draft"))
    category = str(node.get("category", "fact"))
    domain = str(node.get("domain", "general"))
    operation = str(node.get("operation", ""))
    _OPERATION_LABEL = {
        "draft": "📝 Draft", "refine": "🔧 Refined", "merge": "🔗 Merged",
        "supersede": "⬆ Superseded", "debug": "🐛 Debugged", "canonize": "✅ Canonized", "deprecate": "🗑 Deprecated",
    }
    operation_label = _OPERATION_LABEL.get(operation, operation.title())
    confidence = float(node.get("confidence", 0))
    source = str(node.get("source", ""))
    evidence_raw = str(node.get("evidence", "[]"))
    merged_from_raw = str(node.get("merged_from", "[]"))
    contradicts_raw = str(node.get("contradicts", "[]"))
    verified_by_raw = str(node.get("verified_by", "[]"))
    created_at = str(node.get("created_at", ""))[:19]
    refined_at = str(node.get("refined_at", ""))[:19] if node.get("refined_at") else ""
    verified_at = str(node.get("verified_at", ""))[:19] if node.get("verified_at") else ""
    deprecated_at = str(node.get("deprecated_at", ""))[:19] if node.get("deprecated_at") else ""
    retrieval_count = int(node.get("retrieval_count", 0))
    last_used_at = str(node.get("last_used_at", ""))[:19] if node.get("last_used_at") else ""
    correction_count = int(node.get("correction_count", 0))

    # -- Confidence bar (larger, detail view) --
    pct = max(0, min(100, int(confidence * 100)))
    if pct >= 70:
        conf_color = "var(--success)"
    elif pct >= 40:
        conf_color = "var(--warning)"
    else:
        conf_color = "var(--danger)"
    confidence_html = (
        f'<div style="display:flex;align-items:center;gap:12px">'
        f'<div style="flex:1;height:10px;background:var(--border-hover);border-radius:5px;overflow:hidden">'
        f'<div style="width:{pct}%;height:100%;background:{conf_color};border-radius:5px;transition:width .4s var(--ease-out)"></div>'
        f'</div>'
        f'<span style="font-size:1.1rem;font-weight:700;color:{conf_color}">{pct}%</span>'
        f'</div>'
    )

    # -- Evidence list --
    import json as _json
    try:
        evidence_list = _json.loads(evidence_raw) if evidence_raw else []
    except Exception:
        evidence_list = []
    evidence_html = ""
    for ev in evidence_list:
        evidence_html += f'<div style="padding:4px 0;font-size:.88rem;color:var(--ink);border-bottom:1px solid var(--border)">• {_html.escape(str(ev))}</div>'
    if not evidence_html:
        evidence_html = f'<div style="color:var(--ink-dim);padding:12px 0;text-align:center"><div style="font-size:1.5rem;margin-bottom:4px">📋</div><div style="font-style:italic" data-i18n="kd_no_evidence">{_pt("kd_no_evidence")}</div><div style="font-size:.78rem;margin-top:4px;color:var(--ink-muted)" data-i18n="kd_no_evidence_hint">{_pt("kd_no_evidence_hint")}</div></div>'

    # -- Merged from / Contradicts / Verified by --
    try:
        merged_list = _json.loads(merged_from_raw) if merged_from_raw else []
    except Exception:
        merged_list = []
    try:
        contradict_list = _json.loads(contradicts_raw) if contradicts_raw else []
    except Exception:
        contradict_list = []
    try:
        verified_list = _json.loads(verified_by_raw) if verified_by_raw else []
    except Exception:
        verified_list = []

    def _id_list_html(items: list, base_url: str = "/knowledge/") -> str:
        if not items:
            return f'<span style="color:var(--ink-dim);font-style:italic" data-i18n="kd_none_yet">{_pt("kd_none_yet")}</span>'
        parts = []
        for item_id in items:
            sid = _html.escape(str(item_id))
            parts.append(f'<a href="{base_url}{sid}" style="font-family:var(--font-mono);font-size:.82rem">{sid[:16]}…</a>')
        return " ".join(parts)

    # -- Relationships section --
    rel_cards = ""

    if parent_node:
        pid = str(parent_node.get("id", ""))[:16]
        psummary = str(parent_node.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(parent_node.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">⬆ {_pt("kd_parent")}</span>
  <span class="kn-rel-summary">{_html.escape(psummary)}</span>
  <span class="kn-rel-id">{_html.escape(pid)}…</span>
</a>"""

    if supersedes_node:
        sid = str(supersedes_node.get("id", ""))[:16]
        ssummary = str(supersedes_node.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(supersedes_node.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">⬅ {_pt("kd_supersedes")}</span>
  <span class="kn-rel-summary">{_html.escape(ssummary)}</span>
  <span class="kn-rel-id">{_html.escape(sid)}…</span>
</a>"""

    for child in child_nodes:
        cid = str(child.get("id", ""))[:16]
        csummary = str(child.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(child.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">⬇ {_pt("kd_child")}</span>
  <span class="kn-rel-summary">{_html.escape(csummary)}</span>
  <span class="kn-rel-id">{_html.escape(cid)}…</span>
</a>"""

    for sup in superseded_by:
        sid2 = str(sup.get("id", ""))[:16]
        ssummary2 = str(sup.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(sup.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">➡ {_pt("kd_superseded_by")}</span>
  <span class="kn-rel-summary">{_html.escape(ssummary2)}</span>
  <span class="kn-rel-id">{_html.escape(sid2)}…</span>
</a>"""

    for con in contradicts_nodes:
        conid = str(con.get("id", ""))[:16]
        cons = str(con.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(con.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">⚡ {_pt("kd_contradicts")}</span>
  <span class="kn-rel-summary">{_html.escape(cons)}</span>
  <span class="kn-rel-id">{_html.escape(conid)}…</span>
</a>"""

    if not rel_cards:
        rel_cards = f'<div style="color:var(--ink-dim);padding:12px 0;text-align:center"><div style="font-size:1.5rem;margin-bottom:4px">🔗</div><div style="font-style:italic" data-i18n="kd_no_relationships">{_pt("kd_no_relationships")}</div><div style="font-size:.78rem;margin-top:4px;color:var(--ink-muted)" data-i18n="kd_no_relationships_hint">{_pt("kd_no_relationships_hint")}</div></div>'

    # -- Thought chain timeline --
    _ACTION_ICON = {
        "dedup_check": "🔍",
        "merge": "🔗",
        "refine": "✏️",
        "contradiction_detect": "⚡",
        "canonize": "✅",
        "deprecate": "🗑️",
        "create": "🆕",
    }
    _DECISION_COLOR = {
        "create": "var(--success)",
        "merge": "var(--primary)",
        "refine": "var(--info)",
        "ignore": "var(--ink-dim)",
        "flag_contradiction": "var(--danger)",
        "canonize": "var(--success)",
        "deprecate": "var(--warning)",
    }

    timeline_html = ""
    for tc in (thought_chains or []):
        tc_action = str(tc.get("action", ""))
        tc_reasoning = str(tc.get("reasoning", ""))
        tc_decision = str(tc.get("decision", ""))
        tc_conf = float(tc.get("confidence_in_decision", 0) or 0)
        tc_created = str(tc.get("created_at", ""))[:19]
        icon = _ACTION_ICON.get(tc_action, "📝")
        dec_color = _DECISION_COLOR.get(tc_decision, "var(--ink-muted)")

        timeline_html += f"""<div class="kn-tl-item">
  <div class="kn-tl-dot" style="background:{dec_color}"></div>
  <div class="kn-tl-content">
    <div class="kn-tl-header">
      <span>{icon} <strong>{_html.escape(tc_action.replace('_', ' ').title())}</strong></span>
      <span class="kn-tl-time">{_html.escape(tc_created)}</span>
    </div>
    <div class="kn-tl-reasoning">{_html.escape(tc_reasoning)}</div>
    <div class="kn-tl-meta">
      <span>{_pt("kd_decision")}: <strong style="color:{dec_color}">{_html.escape(tc_decision)}</strong></span>
      <span>{_pt("kd_tl_confidence")}: {int(tc_conf * 100)}%</span>
    </div>
  </div>
</div>"""

    if not timeline_html:
        timeline_html = f'<div style="color:var(--ink-dim);padding:16px 0;text-align:center"><div style="font-size:1.5rem;margin-bottom:4px">🧠</div><div style="font-style:italic" data-i18n="kd_no_thought">{_pt("kd_no_thought")}</div><div style="font-size:.78rem;margin-top:4px;color:var(--ink-muted)" data-i18n="kd_no_thought_hint">{_pt("kd_no_thought_hint")}</div></div>'

    # -- Action buttons --
    btns = ""
    btns += (
        f'<button class="btn" style="background:var(--surface);border:1px solid var(--border)" onclick="showEditModal()" data-i18n="kd_edit">{_pt("kd_edit")}</button>'
    )
    next_stage = {"draft": "refined", "refined": "verified", "verified": "canonized"}
    if stage in next_stage:
        nxt = next_stage[stage]
        btns += (
            f'<button class="btn btn-approve" onclick="knPromote(&apos;/api/knowledge/{_html.escape(nid)}/stage&apos;,&apos;{_html.escape(nxt)}&apos;)">'
            f'⬆ {_pt("kd_promote")} {_html.escape(nxt.title())} <kbd>P</kbd></button>'
        )
    if stage not in ("deprecated",):
        btns += (
            f'<button class="btn btn-reject" onclick="knDeprecate(&apos;/api/knowledge/{_html.escape(nid)}/stage&apos;)">'
            f'🗑 {_pt("kd_deprecate")} <kbd>D</kbd></button>'
        )
    else:
        btns += (
            f'<button class="btn btn-reject" style="background:var(--danger-muted);color:var(--danger)" onclick="knDelete(&apos;/api/knowledge/{_html.escape(nid)}&apos;)">'
            f'🗑 {_pt("kd_delete_perm")}</button>'
        )
    # Merge buttons for contradicted nodes
    if contradict_list:
        for cid in contradict_list:
            cid_esc = _html.escape(str(cid))
            btns += (
                f'<button class="btn" style="background:var(--primary);color:#fff" '
                f'onclick="knMerge(&apos;/api/knowledge/{cid_esc}/merge/{_html.escape(nid)}&apos;, '
                f'&apos;Merge this node into {cid_esc[:8]}…&apos;)">'
                f'🔗 {_pt("kd_merge_into")} {cid_esc[:8]}… </button>'
            )
    if not btns:
        btns = f'<div class="empty" style="flex:1">{_pt("kd_no_actions").replace("{stage}", _stage_badge(stage))}</div>'

    body = f"""
<div class="detail-header">
  <a href="/knowledge" class="back-link" data-i18n="kd_back">{_pt("kd_back")}</a>
  <span class="detail-title">{_html.escape(summary[:60])}</span>
  {_stage_badge(stage)}
  {_kn_category_badge(category)}
</div>

<div class="detail-body">

  <!-- Summary & Confidence -->
  <div class="section">
    <h3 data-i18n="kd_summary">{_pt("kd_summary")}</h3>
    <p style="font-size:1rem;font-weight:500">{_html.escape(summary)}</p>
  </div>

  <div class="section">
    <h3 data-i18n="kd_confidence">{_pt("kd_confidence")}</h3>
    {confidence_html}
  </div>

  <!-- Full content -->
  <div class="section">
    <h3 data-i18n="kd_content">{_pt("kd_content")}</h3>
    <p style="white-space:pre-wrap">{_html.escape(content)}</p>
  </div>

  <!-- Metadata grid -->
  <div class="meta-grid" style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);margin-bottom:var(--sp-lg)">
    <span class="label" data-i18n="kd_node_id">{_pt("kd_node_id")}</span><span class="value" style="font-family:var(--font-mono);font-size:.78rem;word-break:break-all">{_html.escape(nid)}</span>
    <span class="label" data-i18n="kd_category">{_pt("kd_category")}</span><span class="value">{_kn_category_badge(category)}</span>
    <span class="label" data-i18n="kd_domain">{_pt("kd_domain")}</span><span class="value">{_html.escape(domain)}</span>
    <span class="label" data-i18n="kd_stage">{_pt("kd_stage")}</span><span class="value">{_stage_badge(stage)}</span>
    <span class="label" data-i18n="kd_operation">{_pt("kd_operation")}</span><span class="value">{_html.escape(operation_label)}</span>
    <span class="label" data-i18n="kd_source_label">{_pt("kd_source_label")}</span><span class="value" style="font-size:.82rem;word-break:break-all">{_html.escape(source)}</span>
    <span class="label" data-i18n="kd_created">{_pt("kd_created")}</span><span class="value">{_html.escape(created_at)}</span>
    {f'<span class="label" data-i18n="kd_refined">{_pt("kd_refined")}</span><span class="value">' + _html.escape(refined_at) + '</span>' if refined_at else ''}
    {f'<span class="label" data-i18n="kd_verified">{_pt("kd_verified")}</span><span class="value">' + _html.escape(verified_at) + '</span>' if verified_at else ''}
    {f'<span class="label" data-i18n="kd_deprecated">{_pt("kd_deprecated")}</span><span class="value">' + _html.escape(deprecated_at) + '</span>' if deprecated_at else ''}
    <span class="label" data-i18n="kd_retrievals">{_pt("kd_retrievals")}</span><span class="value">{retrieval_count}</span>
    <span class="label" data-i18n="kd_last_used">{_pt("kd_last_used")}</span><span class="value">{_html.escape(last_used_at) if last_used_at else '—'}</span>
    <span class="label" data-i18n="kd_corrections">{_pt("kd_corrections")}</span><span class="value">{correction_count}</span>
  </div>

  <!-- Evidence -->
  <div class="section">
    <h3 data-i18n="kd_evidence">{_pt("kd_evidence")}</h3>
    {evidence_html}
  </div>

  <!-- Provenance (merged/contradicts/verified) -->
  <div class="section">
    <h3 data-i18n="kd_provenance">{_pt("kd_provenance")}</h3>
    <div style="display:grid;gap:8px">
      <div><span style="color:var(--ink-muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em" data-i18n="kd_merged_from">{_pt("kd_merged_from")}</span><div style="margin-top:2px">{_id_list_html(merged_list)}</div></div>
      <div><span style="color:var(--ink-muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em" data-i18n="kd_contradicts_list">{_pt("kd_contradicts_list")}</span><div style="margin-top:2px">{_id_list_html(contradict_list)}</div></div>
      <div><span style="color:var(--ink-muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em" data-i18n="kd_verified_by">{_pt("kd_verified_by")}</span><div style="margin-top:2px">{_id_list_html(verified_list)}</div></div>
    </div>
  </div>

  <!-- Relationships -->
  <div class="section">
    <h3 data-i18n="kd_relationships">{_pt("kd_relationships")}</h3>
    <div style="display:flex;flex-direction:column;gap:6px">{rel_cards}</div>
  </div>

  <!-- Thought Chain Timeline -->
  <div class="section">
    <h3 data-i18n="kd_thought_chain">{_pt("kd_thought_chain")}</h3>
    <div class="kn-timeline">{timeline_html}</div>
  </div>

</div>

<div class="action-bar">{btns}</div>

<div id="edit-modal-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;align-items:center;justify-content:center" onclick="if(event.target===this)hideEditModal()">
  <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-lg);max-width:600px;width:90%;max-height:80vh;overflow-y:auto">
    <h2 style="margin-bottom:var(--sp-md);font-size:1.1rem" data-i18n="kd_edit_title">{_pt("kd_edit_title")}</h2>
    <form id="edit-node-form" onsubmit="return submitEdit(event)">
      <label style="display:block;font-size:.78rem;color:var(--ink-muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em">Summary</label>
      <input type="text" id="edit-summary" value="{_html.escape(summary)}" style="width:100%;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);color:var(--ink);font-size:.9rem;margin-bottom:12px;outline:none" onfocus="this.style.borderColor='var(--border-focus)'" onblur="this.style.borderColor='var(--border)'">
      <label style="display:block;font-size:.78rem;color:var(--ink-muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em">Content</label>
      <textarea id="edit-content" rows="8" style="width:100%;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);color:var(--ink);font-size:.84rem;margin-bottom:12px;outline:none;resize:vertical;font-family:var(--font-mono)" onfocus="this.style.borderColor='var(--border-focus)'" onblur="this.style.borderColor='var(--border)'">{_html.escape(content)}</textarea>
      <div style="display:flex;gap:12px;margin-bottom:12px">
        <div style="flex:1">
          <label style="display:block;font-size:.78rem;color:var(--ink-muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em">Category</label>
          <select id="edit-category" style="width:100%;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);color:var(--ink);font-size:.84rem;outline:none">
            <option value="fact"{" selected" if category=="fact" else ""}>fact</option>
            <option value="rule"{" selected" if category=="rule" else ""}>rule</option>
            <option value="workflow_hint"{" selected" if category=="workflow_hint" else ""}>workflow_hint</option>
            <option value="preference"{" selected" if category=="preference" else ""}>preference</option>
          </select>
        </div>
        <div style="flex:1">
          <label style="display:block;font-size:.78rem;color:var(--ink-muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em">Domain</label>
          <input type="text" id="edit-domain" value="{_html.escape(domain)}" list="domain-list" style="width:100%;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);color:var(--ink);font-size:.84rem;outline:none" onfocus="this.style.borderColor='var(--border-focus)'" onblur="this.style.borderColor='var(--border)'">
          <datalist id="domain-list">
            <option value="general"><option value="devops"><option value="study"><option value="network"><option value="security">
          </datalist>
        </div>
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button type="button" class="kn-action-btn secondary" onclick="hideEditModal()" data-i18n="kd_cancel">{_pt("kd_cancel")}</button>
        <button type="submit" class="kn-action-btn" data-i18n="kd_save">{_pt("kd_save")}</button>
      </div>
    </form>
  </div>
</div>

<div class="confirm-overlay" id="confirm-overlay" onclick="if(event.target===this)hideConfirm()">
  <div class="confirm-modal" id="confirm-modal">
    <h3 id="confirm-title"></h3>
    <div class="confirm-actions">
      <button class="btn-yes" id="confirm-action-btn" data-i18n="rv_confirm">{_pt("rv_confirm")}</button>
      <button class="btn-no" onclick="hideConfirm()" data-i18n="kd_cancel">{_pt("kd_cancel")}</button>
    </div>
  </div>
</div>

<style>
.kn-rel-card{{
  display:flex;align-items:center;gap:10px;padding:10px 14px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  text-decoration:none;color:var(--ink);transition:all var(--duration);min-height:44px
}}
.kn-rel-card:hover{{border-color:var(--border-focus);background:var(--card-hover);text-decoration:none}}
.kn-rel-type{{font-size:.72rem;font-weight:600;color:var(--primary);min-width:100px;white-space:nowrap}}
.kn-rel-summary{{flex:1;font-size:.84rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.kn-rel-id{{font-size:.72rem;color:var(--ink-dim);font-family:var(--font-mono);flex-shrink:0}}

.kn-timeline{{position:relative;padding-left:28px}}
.kn-tl-item{{position:relative;padding-bottom:20px}}
.kn-tl-item:last-child{{padding-bottom:0}}
.kn-tl-item::before{{
  content:'';position:absolute;left:-22px;top:24px;bottom:0;
  width:2px;background:linear-gradient(to bottom,var(--primary) 0%,var(--border) 100%);
  border-radius:1px
}}
.kn-tl-item:last-child::before{{display:none}}
.kn-tl-dot{{
  position:absolute;left:-26px;top:4px;width:14px;height:14px;
  border-radius:50%;border:2px solid var(--card);z-index:1;
  box-shadow:0 0 8px rgba(0,0,0,.3),0 0 0 3px var(--surface)
}}
.kn-tl-content{{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  padding:12px 16px;transition:border-color var(--duration),box-shadow var(--duration);
  position:relative;overflow:hidden
}}
.kn-tl-content::before{{
  content:'';position:absolute;left:0;top:8px;bottom:8px;width:3px;
  border-radius:2px;background:var(--primary);opacity:.4;transition:opacity var(--duration)
}}
.kn-tl-content:hover{{border-color:var(--primary);box-shadow:0 2px 12px rgba(167,139,250,.12)}}
.kn-tl-content:hover::before{{opacity:1}}
.kn-tl-header{{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}}
.kn-tl-time{{font-size:.72rem;color:var(--ink-dim);font-family:var(--font-mono)}}
.kn-tl-reasoning{{font-size:.84rem;color:var(--ink);margin-top:8px;line-height:1.6;white-space:pre-wrap;word-break:break-word}}
.kn-tl-meta{{display:flex;gap:16px;margin-top:8px;font-size:.75rem;color:var(--ink-muted)}}
</style>
"""
    return _page(f"Knowledge · {summary[:40]}", body, extra_js=_KN_ACTION_JS, nav_active="knowledge")


