// CatBa page: the UI boundary for the root page.
//
// Receives props from route.py's GET handler. TSX compilation is not
// implemented yet; this is a placeholder component.

type Props = {
    message: string
}

export default function Page({ message }: Props) {
    return (
        <main>
            <h1>{message}</h1>
        </main>
    )
}
