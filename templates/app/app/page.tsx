import { Head } from "@inertiajs/react"

type Props = {
    message: string
}

export default function Page({ message }: Props) {
    return (
        <main>
            <Head title="CatBa App" />
            <h1>{message}</h1>
            <p>Welcome to your CatBa application with React and Inertia.</p>
        </main>
    )
}
