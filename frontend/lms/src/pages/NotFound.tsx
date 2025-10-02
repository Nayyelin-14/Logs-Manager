import { Button } from "../components/ui/button";
import { Link } from "react-router-dom";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
// import { Icons } from "../components/icons";

const NotFound = () => {
  return (
    <div className=" flex flex-col min-h-screen over-hidden">
      <main className="flex items-center mx-auto flex-1 my-32 lg:my-0 ">
        {/* flex-1: Makes an element grow to fill the remaining space inside a flex
        container. */}
        <Card className="w-[400px] md:w-[500px]">
          <CardHeader className="flex flex-col items-center gap-4">
            <CardTitle>Oops!!!</CardTitle>
            <CardDescription>404!!! Not Found</CardDescription>
          </CardHeader>

          <CardFooter className="flex justify-center">
            <Button variant={"outline"} asChild>
              <Link to="/">Go to Home Page</Link>
            </Button>
          </CardFooter>
        </Card>
      </main>
    </div>
  );
};

export default NotFound;
