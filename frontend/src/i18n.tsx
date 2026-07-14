import { ReactNode, createContext, useContext, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { LanguageCode, getSettings } from "./lib/api";

const messages = {
  "zh-TW": {dashboard:"總覽",setup:"設定精靈",providers:"模型與端點",codex:"Codex 驗證",projects:"專案",decisions:"決策",actions:"行動項目",knowledge:"知識庫",meetings:"會議",history:"歷史",diagnostics:"診斷",settings:"設定",access:"存取控制",local:"本機優先",save:"儲存設定",loading:"載入中",systemSettings:"系統設定"},
  "zh-CN": {dashboard:"总览",setup:"设置向导",providers:"模型与端点",codex:"Codex 验证",projects:"项目",decisions:"决策",actions:"行动项目",knowledge:"知识库",meetings:"会议",history:"历史",diagnostics:"诊断",settings:"设置",access:"访问控制",local:"本地优先",save:"保存设置",loading:"加载中",systemSettings:"系统设置"},
  en: {dashboard:"Dashboard",setup:"Setup",providers:"Models & endpoints",codex:"Codex auth",projects:"Projects",decisions:"Decisions",actions:"Action items",knowledge:"Knowledge",meetings:"Meetings",history:"History",diagnostics:"Diagnostics",settings:"Settings",access:"Access control",local:"Local first",save:"Save settings",loading:"Loading",systemSettings:"System settings"},
  ja: {dashboard:"概要",setup:"セットアップ",providers:"モデルと接続先",codex:"Codex 認証",projects:"プロジェクト",decisions:"意思決定",actions:"アクション",knowledge:"ナレッジ",meetings:"会議",history:"履歴",diagnostics:"診断",settings:"設定",access:"アクセス制御",local:"ローカル優先",save:"設定を保存",loading:"読み込み中",systemSettings:"システム設定"},
  ko: {dashboard:"대시보드",setup:"설정 마법사",providers:"모델 및 엔드포인트",codex:"Codex 인증",projects:"프로젝트",decisions:"결정",actions:"작업 항목",knowledge:"지식",meetings:"회의",history:"기록",diagnostics:"진단",settings:"설정",access:"접근 제어",local:"로컬 우선",save:"설정 저장",loading:"불러오는 중",systemSettings:"시스템 설정"},
} as const;

type MessageKey = keyof typeof messages.en;
type I18nValue = {language:LanguageCode;t:(key:MessageKey)=>string};
const I18nContext=createContext<I18nValue>({language:"zh-TW",t:key=>messages["zh-TW"][key]});

export function I18nProvider({children}:{children:ReactNode}){
  const settings=useQuery({queryKey:["settings"],queryFn:getSettings,staleTime:30_000});
  const language=settings.data?.ui_language??"zh-TW";
  useEffect(()=>{document.documentElement.lang=language},[language]);
  return <I18nContext.Provider value={{language,t:key=>messages[language][key]}}>{children}</I18nContext.Provider>;
}

export const useI18n=()=>useContext(I18nContext);
