import { AuthForm } from "../../AppComponents/Forms/AuthForm";

function RegisterPage() {
  return (
    <div className="flex w-full h-screen place-content-center px-4  overflow-hidden">
      <AuthForm formName="register" />
    </div>
  );
}

export default RegisterPage;
