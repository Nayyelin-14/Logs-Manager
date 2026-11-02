import { useActionData } from "react-router";
import { AuthForm } from "../../AppComponents/Forms/AuthForm";

import { toast } from "sonner";
import { useEffect } from "react";
function LoginPage() {
  const actionData = useActionData();
  useEffect(() => {
    if (actionData) {
      toast.error(
        actionData.message ?? actionData.error ?? "Sign in failed. Please try again."
      );
    }
  }, [actionData]);
  return (
    <div className="w-full">
      <AuthForm formName="login" />
    </div>
  );
}

export default LoginPage;
