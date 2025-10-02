import { useActionData } from "react-router";
import { AuthForm } from "../../AppComponents/Forms/AuthForm";

import { toast } from "sonner";
import { useEffect } from "react";
function LoginPage() {
  const actionData = useActionData();
  console.log(actionData);
  useEffect(() => {
    if (actionData) {
      if (actionData?.isSuccess === false) {
        toast.error(actionData.message);
      } else {
        toast.success(actionData.message);
      }
    }
  }, [actionData]);
  return (
    <div className="flex w-full min-h-screen place-content-center px-4  overflow-hidden">
      <AuthForm formName="login" />
    </div>
  );
}

export default LoginPage;
