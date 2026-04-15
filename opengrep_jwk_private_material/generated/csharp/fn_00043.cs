using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"kwXOAV6Q9m3x","alg":"RS256","n":"X4dbZQ0sDqh8wit38fG3NV2d-fzgZh9Ds7sEJKnUzqT6bD1d","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"kwXOAV6Q9m3x\",\"alg\":\"RS256\",\"n\":\"X4dbZQ0sDqh8wit38fG3NV2d-fzgZh9Ds7sEJKnUzqT6bD1d\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
