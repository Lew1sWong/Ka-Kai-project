import VerifyEmailClient from "./VerifyEmailClient";

type VerifyEmailPageProps = {
  searchParams?: Promise<{
    token?: string;
  }>;
};

export default async function VerifyEmailPage({ searchParams }: VerifyEmailPageProps) {
  const resolvedSearchParams = await searchParams;
  return <VerifyEmailClient token={resolvedSearchParams?.token ?? null} />;
}
