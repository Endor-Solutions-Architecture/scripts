using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
    var jwk = "{\"kty\":\"oct\",\"kid\":\"missing-k\",\"alg\":\"HS256\"}";
    var key = new JsonWebKey(jwk);
  }
}
