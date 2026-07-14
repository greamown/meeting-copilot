import { Component, ErrorInfo, ReactNode } from "react";

export class ErrorBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true}}
  componentDidCatch(error:Error,info:ErrorInfo){console.error("UI boundary",error.name,info.componentStack)}
  render(){return this.state.failed?<main className="page"><div className="alert error"><strong>頁面無法顯示。</strong> 請重新載入；會議與逐字稿仍保存在後端。</div><button className="button" onClick={()=>location.reload()}>重新載入</button></main>:this.props.children}
}
