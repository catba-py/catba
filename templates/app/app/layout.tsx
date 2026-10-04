import { ReactNode } from "react"

export default function RootLayout({ children }: { children: ReactNode }) {
    return (
        <div className="catba-app-shell">
            <header style={{ padding: "1rem 2rem", borderBottom: "1px solid #e5e7eb", background: "#f9fafb" }}>
                <nav style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: "bold", fontSize: "1.2rem" }}>CatBa</span>
                    <span>Next.js for Python</span>
                </nav>
            </header>
            <div style={{ padding: "2rem" }}>
                {children}
            </div>
        </div>
    )
}
