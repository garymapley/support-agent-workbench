import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "售后工单工作台",
  description: "处理工单、追踪 Agent 工具调用并完成人工退款审批。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
