import { useEffect } from "react";
import { ConfirmPwdForm } from "../../AppComponents/Forms/ConfirmPwdForm";
import useAuthStore from "../../store/authStore";
import { toast } from "sonner";

export default function ConfirmPwdPage() {
  const auth = useAuthStore();
  const message = useAuthStore((state) => state.message);
  console.log(auth);
  useEffect(() => {
    if (message) {
      toast.success(message);
    }
  }, [message]);
  return (
    <div className="bg-background flex min-h-svh flex-col items-center justify-center gap-6 p-6 md:p-10">
      <div className="w-full max-w-sm">
        <ConfirmPwdForm />
      </div>
    </div>
  );
}
