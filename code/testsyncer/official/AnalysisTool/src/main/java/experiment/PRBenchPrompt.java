package experiment;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import com.google.gson.*;
import promptmaker.PromptMaker;
public class PRBenchPrompt {
    public static void main(String[] args) throws Exception {
        JsonObject input = new JsonParser().parse(new String(Files.readAllBytes(Paths.get(args[0])), StandardCharsets.UTF_8)).getAsJsonObject();
        PromptMaker maker = new PromptMaker();
        maker.setoldprojectpath(input.get("old_project").getAsString());
        maker.setnewprojectpath(input.get("new_project").getAsString());
        maker.setoldclasspath(input.get("old_file").getAsString());
        maker.setnewclasspath(input.get("new_file").getAsString());
        maker.setoldmethodcontent(input.get("old_method").getAsString());
        maker.setnewmethodcontent(input.get("new_method").getAsString());
        maker.setoldtestcontent(input.get("old_test").getAsString());
        String prompt = maker.getPrompt();
        if (prompt == null || prompt.trim().isEmpty()) throw new IllegalStateException("Author PromptMaker returned an empty prompt");
        Files.write(Paths.get(args[1]), prompt.getBytes(StandardCharsets.UTF_8));
    }
}
