import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { AuthLayout } from "../components/AuthLayout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/inputs";
import { Spinner } from "../components/ui/spinner";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function RegisterPage() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(email.trim(), password, fullName.trim());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start asking questions of your documents."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-teal hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label htmlFor="name" className="mb-1.5 block text-sm font-medium">
            Full name
          </label>
          <Input
            id="name"
            autoComplete="name"
            required
            maxLength={120}
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="email" className="mb-1.5 block text-sm font-medium">
            Email
          </label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="password" className="mb-1.5 block text-sm font-medium">
            Password
          </label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={128}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <p className="mt-1.5 text-xs text-navy-soft">At least 8 characters.</p>
        </div>
        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={busy}>
          {busy && <Spinner />}
          Create account
        </Button>
      </form>
    </AuthLayout>
  );
}
