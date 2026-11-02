import { useEffect } from "react";
import { ConfirmPwdForm } from "../../AppComponents/Forms/ConfirmPwdForm";
import useAuthStore from "../../store/authStore";
import { toast } from "sonner";

export default function ConfirmPwdPage() {
  const message = useAuthStore((state) => state.message);
  useEffect(() => {
    if (message) {
      toast.success(message);
    }
  }, [message]);
  return (
    <div className="w-full">
      <ConfirmPwdForm />
    </div>
  );
}
