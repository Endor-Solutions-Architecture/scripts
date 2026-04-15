using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"oct","kid":"25awqREkmcS5","alg":"HS256","k":"_tj3OWI7Rl6CP6RHjlIFHUNG3vBlfxKRiA211dYPZNWcW_in6SXrUnn1noy9e0Sr"}
    var jwk = "{\"kty\":\"oct\",\"kid\":\"25awqREkmcS5\",\"alg\":\"HS256\",\"k\":\"_tj3OWI7Rl6CP6RHjlIFHUNG3vBlfxKRiA211dYPZNWcW_in6SXrUnn1noy9e0Sr\"}";
    var key = new JsonWebKey(jwk);
  }
}
